"""Durable leased worker service for processing inductive batch scoring jobs."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    BatchAnalysis,
    BatchAnalysisRow,
    FraudPrediction,
    GraphSnapshot,
    InductiveInferenceJob,
    InductivePredictionEvidence,
    InferenceRun,
    Review,
)
from app.services.batch_csv import BatchReviewInput, PermittedHistoricContext
from app.services.batch_graph import load_permitted_historic_context
from app.services.inductive_yelpchi import (
    BundleVerificationError,
    InductiveYelpChiRuntime,
    InsufficientContextError,
    ScopeIncompatibilityError,
    get_inductive_runtime,
)

logger = logging.getLogger("neurograph.inductive_worker")


def acquire_next_job(
    db: Session,
    worker_id: str = "inductive-worker-1",
    lease_duration: timedelta = timedelta(minutes=5),
) -> InductiveInferenceJob | None:
    """Acquire a durable lease on the next eligible queued or retry_wait job."""
    now = datetime.now(timezone.utc)
    # Check for queued, retry_wait ready for retry, or stale running lease
    stmt = (
        select(InductiveInferenceJob)
        .where(
            (InductiveInferenceJob.status.in_(["queued"]))
            | (
                (InductiveInferenceJob.status == "retry_wait")
                & (
                    (InductiveInferenceJob.next_attempt_at.is_(None))
                    | (InductiveInferenceJob.next_attempt_at <= now)
                )
            )
            | (
                (InductiveInferenceJob.status == "running")
                & (InductiveInferenceJob.lease_expires_at.is_not(None))
                & (InductiveInferenceJob.lease_expires_at < now)
            )
        )
        .order_by(InductiveInferenceJob.priority.asc(), InductiveInferenceJob.created_at.asc())
        .limit(1)
    )

    job = db.scalar(stmt)
    if job is None:
        return None

    job.status = "running"
    job.worker_id = worker_id
    job.lease_token = str(uuid.uuid4())
    job.lease_expires_at = now + lease_duration
    job.attempt_count += 1
    if job.started_at is None:
        job.started_at = now
    job.updated_at = now
    db.commit()
    db.refresh(job)
    return job


def process_inductive_job(
    job_id: int,
    db: Session,
    runtime: InductiveYelpChiRuntime | None = None,
) -> bool:
    """Execute inductive scoring for a leased job, writing real predictions and evidence."""
    job = db.get(InductiveInferenceJob, job_id)
    if job is None or job.status != "running":
        return False

    run = db.get(InferenceRun, job.inference_run_id)
    if run is None:
        job.status = "failed"
        job.last_error_code = "inference_run_not_found"
        job.last_error = f"InferenceRun {job.inference_run_id} not found."
        db.commit()
        return False

    batch = db.scalar(select(BatchAnalysis).where(BatchAnalysis.inference_run_id == run.inference_run_id))

    snapshot = db.get(GraphSnapshot, run.graph_snapshot_id)
    if snapshot is None:
        return _fail_job(
            db, job, run, batch,
            error_code="snapshot_not_found",
            message=f"Graph snapshot {run.graph_snapshot_id} was not found."
        )

    if snapshot.storage_status != "available" or not snapshot.batch_context_permitted:
        return _fail_job(
            db, job, run, batch,
            error_code="snapshot_not_permitted",
            message="Graph snapshot is not available or not permitted for batch context."
        )

    # Load accepted batch reviews
    accepted_rows = db.execute(
        select(BatchAnalysisRow, Review)
        .join(Review, Review.review_id == BatchAnalysisRow.review_id)
        .where(
            BatchAnalysisRow.batch_analysis_id == batch.batch_analysis_id if batch else False,
            BatchAnalysisRow.row_state == "accepted",
        )
        .order_by(BatchAnalysisRow.row_number)
    ).all() if batch else []

    if not accepted_rows:
        return _fail_job(
            db, job, run, batch,
            error_code="no_accepted_reviews",
            message="No accepted reviews found for this batch inference run."
        )

    uploaded_inputs: list[BatchReviewInput] = []
    for row, rev in accepted_rows:
        reviewed_at = rev.reviewed_at
        if reviewed_at is not None and reviewed_at.tzinfo is None:
            reviewed_at = reviewed_at.replace(tzinfo=timezone.utc)
        uploaded_inputs.append(
            BatchReviewInput(
                review_id=int(rev.review_id),
                reviewer_id=int(rev.reviewer_id),
                product_id=int(rev.product_id),
                rating=int(rev.rating),
                reviewed_at=reviewed_at or datetime.now(timezone.utc),
                review_text=rev.review_text or "",
                source_review_key=rev.source_review_key,
            )
        )

    try:
        # Load permitted historic context without selecting ground truth or labels
        historic_context = load_permitted_historic_context(
            db, snapshot.graph_snapshot_id, split="train"
        )
    except Exception as exc:
        return _fail_job(
            db, job, run, batch,
            error_code="insufficient_historic_context",
            message=str(exc)
        )

    if runtime is None:
        try:
            runtime = get_inductive_runtime()
        except Exception as exc:
            return _fail_job(
                db, job, run, batch,
                error_code="bundle_verification_failed",
                message=f"Inductive runtime verification failed: {exc}"
            )

    try:
        scored_reviews = runtime.score_batch(uploaded_inputs, historic_context, snapshot)
    except InsufficientContextError as exc:
        return _fail_job(db, job, run, batch, error_code="insufficient_historic_context", message=str(exc))
    except ScopeIncompatibilityError as exc:
        return _fail_job(db, job, run, batch, error_code="snapshot_scope_incompatible", message=str(exc))
    except BundleVerificationError as exc:
        return _fail_job(db, job, run, batch, error_code="bundle_verification_failed", message=str(exc))
    except Exception as exc:
        logger.exception("Unexpected scoring runtime exception for job %s: %s", job_id, exc)
        if job.attempt_count < job.max_attempts:
            job.status = "retry_wait"
            job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=15)
            job.last_error_code = "worker_transient_error"
            job.last_error = str(exc)
            db.commit()
            return False
        else:
            return _fail_job(db, job, run, batch, error_code="worker_execution_failed", message=str(exc))

    # Persist predictions and evidence transactionally
    now = datetime.now(timezone.utc)
    for scored in scored_reviews:
        pred = FraudPrediction(
            inference_run_id=run.inference_run_id,
            review_id=scored.review_id,
            risk_score=round(scored.risk_score, 8),
            predicted_label=scored.predicted_label,
            attention_weights=scored.attention_weights,
            graph_status="inductive_scored",
            created_at=now,
        )
        db.add(pred)
        db.flush()

        evidence = InductivePredictionEvidence(
            fraud_prediction_id=pred.fraud_prediction_id,
            graph_snapshot_id=scored.graph_snapshot_id,
            relation_schema_version=scored.relation_schema_version,
            context_cutoff_at=scored.context_cutoff_at,
            neighbor_counts=scored.neighbor_counts,
            historic_review_ids=scored.historic_review_ids,
            stitched_graph_sha256=scored.stitched_graph_sha256,
            input_feature_sha256=scored.input_feature_sha256,
            embedding_sha256=scored.embedding_sha256,
            bundle_manifest_sha256=scored.bundle_manifest_sha256,
            provenance="real",
            created_at=now,
        )
        db.add(evidence)

    # Update run, job, and batch
    run.status = "completed"
    run.completed_count = len(scored_reviews)
    run.completed_at = now

    job.status = "succeeded"
    job.completed_at = now
    job.updated_at = now

    if batch:
        batch.status = "completed"

    db.commit()
    logger.info("Inductive job %s succeeded for run %s (%s reviews scored)", job_id, run.inference_run_id, len(scored_reviews))
    return True


def _fail_job(
    db: Session,
    job: InductiveInferenceJob,
    run: InferenceRun,
    batch: BatchAnalysis | None,
    error_code: str,
    message: str,
) -> bool:
    """Record a stable failure status without fabricating predictions."""
    now = datetime.now(timezone.utc)
    job.status = "failed"
    job.last_error_code = error_code
    job.last_error = message
    job.completed_at = now
    job.updated_at = now

    run.status = "failed"
    run.completed_at = now

    if batch:
        batch.status = "failed"
        batch.blocking_reasons = [error_code]

    db.commit()
    logger.warning("Inductive job %s failed with code '%s': %s", job.job_id, error_code, message)
    return False
