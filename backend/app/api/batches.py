"""CSV review intake and fail-closed batch-analysis status/results API."""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AuditLog,
    BatchAnalysis,
    BatchAnalysisRow,
    FraudPrediction,
    GraphSnapshot,
    InductiveInferenceJob,
    InductivePredictionEvidence,
    InferenceRun,
    ModelVersion,
    PreprocessingVersion,
    Product,
    Review,
    Reviewer,
    Role,
    User,
)
from app.schemas import BatchContextPermissionRequest
from app.security import current_user, require_roles
from app.services.batch_csv import MAX_CSV_BYTES, parse_review_csv

router = APIRouter(prefix="/api/v1")


def _batch_payload(batch: BatchAnalysis, db: Session | None = None) -> dict:
    payload = {
        "batch_analysis_id": batch.batch_analysis_id,
        "batch_key": batch.batch_key,
        "status": batch.status,
        "row_count": batch.row_count,
        "accepted_count": batch.accepted_count,
        "rejected_count": batch.rejected_count,
        "inference_run_id": batch.inference_run_id,
        "historic_graph_snapshot_id": batch.historic_graph_snapshot_id,
        "upload_sha256": batch.upload_sha256,
        "blocking_reasons": batch.blocking_reasons,
        "created_at": batch.created_at,
    }
    if db is not None and batch.inference_run_id is not None:
        run = db.get(InferenceRun, batch.inference_run_id)
        if run is not None:
            payload["inference_run"] = {
                "inference_run_id": run.inference_run_id,
                "run_key": run.run_key,
                "status": run.status,
                "threshold": float(run.threshold),
                "requested_count": run.requested_count,
                "completed_count": run.completed_count,
                "created_at": run.created_at,
                "completed_at": run.completed_at,
            }
            job = db.scalar(
                select(InductiveInferenceJob).where(
                    InductiveInferenceJob.inference_run_id == run.inference_run_id
                )
            )
            if job is not None:
                payload["job"] = {
                    "job_id": job.job_id,
                    "status": job.status,
                    "attempt_count": job.attempt_count,
                    "max_attempts": job.max_attempts,
                    "worker_id": job.worker_id,
                    "last_error_code": job.last_error_code,
                    "last_error": job.last_error,
                }
    return payload


def _assert_can_read_batch(db: Session, batch: BatchAnalysis, user: User) -> None:
    if batch.requested_by_user_id == user.user_id:
        return
    role = db.get(Role, user.role_id)
    if role is None or role.role_key != "ADMIN":
        raise HTTPException(status_code=404, detail={"code": "batch_analysis_not_found", "message": "Batch analysis was not found."})


@router.patch("/graph-snapshots/{snapshot_id}/batch-context-permission")
def set_batch_context_permission(
    snapshot_id: int,
    payload: BatchContextPermissionRequest,
    actor: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    snapshot = db.get(GraphSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Graph snapshot was not found."})
    if payload.permitted and snapshot.storage_status != "available":
        raise HTTPException(status_code=409, detail={"code": "snapshot_unavailable", "message": "Only an available graph snapshot can be permitted as batch context."})
    before = {
        "batch_context_permitted": snapshot.batch_context_permitted,
        "context_scope_key": snapshot.context_scope_key,
    }
    snapshot.batch_context_permitted = payload.permitted
    if payload.permitted:
        if payload.context_scope_key:
            snapshot.context_scope_key = payload.context_scope_key.strip()
        elif not snapshot.context_scope_key:
            snapshot.context_scope_key = snapshot.snapshot_key or f"scope-{snapshot_id}"
    db.add(AuditLog(actor_user_id=actor.user_id, action="graph_snapshot.batch_context_permission",
                    entity_type="graph_snapshot", entity_key=str(snapshot_id),
                    before_data=before, after_data={
                        "batch_context_permitted": snapshot.batch_context_permitted,
                        "context_scope_key": snapshot.context_scope_key,
                    }))
    db.commit()
    return {
        "graph_snapshot_id": snapshot_id,
        "batch_context_permitted": snapshot.batch_context_permitted,
        "context_scope_key": snapshot.context_scope_key,
    }

def _snapshot_payload(snapshot: GraphSnapshot) -> dict:
    return {
        "graph_snapshot_id": snapshot.graph_snapshot_id,
        "snapshot_key": snapshot.snapshot_key,
        "dataset_name": snapshot.dataset_name,
        "dataset_sha256": snapshot.dataset_sha256,
        "artifact_uri": snapshot.artifact_uri,
        "artifact_sha256": snapshot.artifact_sha256,
        "graph_builder_version": snapshot.graph_builder_version,
        "relation_schema_version": snapshot.relation_schema_version,
        "split_protocol_key": snapshot.split_protocol_key,
        "node_count": snapshot.node_count,
        "edge_counts": snapshot.edge_counts,
        "storage_status": snapshot.storage_status,
        "batch_context_permitted": snapshot.batch_context_permitted,
        "context_scope_key": snapshot.context_scope_key,
        "provenance": snapshot.provenance,
        "created_at": snapshot.created_at,
    }


@router.get("/graph-snapshots")
def list_graph_snapshots(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    snapshots = db.scalars(
        select(GraphSnapshot).order_by(GraphSnapshot.graph_snapshot_id.desc())
    ).all()
    return {"items": [_snapshot_payload(s) for s in snapshots], "total": len(snapshots)}


@router.get("/graph-snapshots/{snapshot_id}")
def get_graph_snapshot(
    snapshot_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    snapshot = db.get(GraphSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Graph snapshot was not found."})
    return _snapshot_payload(snapshot)


@router.post("/batch-analyses", status_code=201)
async def create_batch_analysis(
    file: UploadFile = File(...),
    source_system: str = Form(min_length=1, max_length=100),
    historic_graph_snapshot_id: int | None = Form(default=None, gt=0),
    model_version_id: int | None = Form(default=None, gt=0),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if idempotency_key:
        existing_run = db.scalar(
            select(InferenceRun).where(
                InferenceRun.requested_by_user_id == user.user_id,
                InferenceRun.idempotency_key == idempotency_key,
            )
        )
        if existing_run is not None:
            existing_batch = db.scalar(
                select(BatchAnalysis).where(
                    BatchAnalysis.inference_run_id == existing_run.inference_run_id
                )
            )
            if existing_batch is not None:
                return _batch_payload(existing_batch, db=db)

    content = await file.read(MAX_CSV_BYTES + 1)
    await file.close()
    rows = parse_review_csv(content)
    normalized_source = source_system.strip()
    if not normalized_source:
        raise HTTPException(status_code=422, detail={"code": "invalid_source_system", "message": "source_system must not be empty."})

    snapshot = None
    if historic_graph_snapshot_id is not None:
        snapshot = db.get(GraphSnapshot, historic_graph_snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Graph snapshot was not found."})
        if snapshot.storage_status != "available" or not snapshot.batch_context_permitted:
            raise HTTPException(status_code=409, detail={"code": "snapshot_not_permitted", "message": "The selected graph snapshot is not available and explicitly permitted for batch context."})

    candidate_model = None
    if model_version_id is not None:
        model = db.get(ModelVersion, model_version_id)
        if model is None:
            raise HTTPException(status_code=404, detail={"code": "model_version_not_found", "message": "Model version was not found."})
        if model.provenance == "synthetic_demo":
            raise HTTPException(status_code=409, detail={"code": "synthetic_model_ineligible", "message": "Synthetic demo models are ineligible for verified real inference."})
        if model.lifecycle_status != "verified":
            raise HTTPException(status_code=409, detail={"code": "model_not_verified", "message": "Model is not verified."})
        if model.supported_inference_mode != "inductive_batch_v1":
            raise HTTPException(status_code=409, detail={"code": "unsupported_inference_mode", "message": "Model does not support inductive_batch_v1 mode."})
        candidate_model = model
    else:
        candidate_model = db.scalar(
            select(ModelVersion)
            .join(PreprocessingVersion, PreprocessingVersion.preprocessing_version_id == ModelVersion.preprocessing_version_id)
            .where(
                ModelVersion.provenance == "real",
                ModelVersion.lifecycle_status == "verified",
                ModelVersion.supported_inference_mode == "inductive_batch_v1",
                ModelVersion.checkpoint_uri.is_not(None),
                ModelVersion.checkpoint_sha256.is_not(None),
                PreprocessingVersion.lifecycle_status == "verified",
            )
            .order_by(ModelVersion.model_version_id.desc())
            .limit(1)
        )

    if candidate_model is not None and snapshot is not None:
        is_compatible = (
            snapshot.context_scope_key == "inductive-rur-rsr-rtr-v1"
            or snapshot.relation_schema_version == "inductive-rur-rsr-rtr-v1"
        )
        if not is_compatible:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "snapshot_scope_incompatible",
                    "message": f"Graph snapshot scope '{snapshot.context_scope_key or snapshot.relation_schema_version}' is incompatible with model relation schema 'inductive-rur-rsr-rtr-v1'.",
                },
            )

    row_errors: dict[int, list[dict[str, str]]] = {
        row.row_number: list(row.errors) for row in rows
    }
    upload_keys = [row.uploaded_review_key for row in rows
                   if row.uploaded_review_key is not None and row.accepted]

    try:
        with db.begin_nested():
            existing_keys = set(db.scalars(
                select(Review.source_review_key).where(
                    Review.source_system == normalized_source,
                    Review.source_review_key.in_(upload_keys),
                )
            )) if upload_keys else set()
            for row in rows:
                if row.accepted and row.uploaded_review_key in existing_keys:
                    row_errors[row.row_number].append({
                        "field": "review_id",
                        "code": "already_imported",
                        "message": "review_id already exists for this source_system.",
                    })

            accepted_rows = [row for row in rows if not row_errors[row.row_number]]
            reviewer_keys = {row.reviewer_key for row in accepted_rows if row.reviewer_key}
            product_keys = {row.product_key for row in accepted_rows if row.product_key}
            reviewer_map = {
                item.external_reviewer_key: item for item in db.scalars(
                    select(Reviewer).where(Reviewer.source_system == normalized_source,
                                           Reviewer.external_reviewer_key.in_(reviewer_keys))
                )
            } if reviewer_keys else {}
            product_map = {
                item.external_product_key: item for item in db.scalars(
                    select(Product).where(Product.source_system == normalized_source,
                                           Product.external_product_key.in_(product_keys))
                )
            } if product_keys else {}

            for key in reviewer_keys:
                if key not in reviewer_map:
                    reviewer_map[key] = Reviewer(source_system=normalized_source, external_reviewer_key=key)
                    db.add(reviewer_map[key])
            for key in product_keys:
                if key not in product_map:
                    product_map[key] = Product(source_system=normalized_source, external_product_key=key)
                    db.add(product_map[key])
            db.flush()

            blocking_reasons: list[str] = []
            can_queue = False
            if accepted_rows:
                if candidate_model is None:
                    blocking_reasons.append("verified_model_bundle_not_registered")
                if historic_graph_snapshot_id is None:
                    blocking_reasons.append("historic_graph_snapshot_not_selected")

                if candidate_model is not None and historic_graph_snapshot_id is not None:
                    can_queue = True

            accepted_count = len(accepted_rows)
            rejected_count = len(rows) - accepted_count
            if not accepted_count:
                status = "validation_failed"
            elif can_queue:
                status = "queued"
            else:
                status = "blocked"

            batch = BatchAnalysis(
                requested_by_user_id=user.user_id,
                source_system=normalized_source,
                historic_graph_snapshot_id=historic_graph_snapshot_id,
                upload_sha256=hashlib.sha256(content).hexdigest(),
                row_count=len(rows), accepted_count=accepted_count,
                rejected_count=rejected_count, status=status,
                blocking_reasons=blocking_reasons,
            )
            db.add(batch)
            db.flush()

            for row in rows:
                errors = row_errors[row.row_number]
                review_id = None
                row_state = "rejected"
                if not errors:
                    review = Review(
                        source_system=normalized_source,
                        source_review_key=row.uploaded_review_key,
                        reviewer_id=reviewer_map[row.reviewer_key].reviewer_id,
                        product_id=product_map[row.product_key].product_id,
                        submitted_by_user_id=user.user_id,
                        rating=row.rating,
                        reviewed_at=row.reviewed_at,
                        review_text=row.review_text,
                    )
                    db.add(review)
                    db.flush()
                    review_id = review.review_id
                    row_state = "accepted"
                db.add(BatchAnalysisRow(
                    batch_analysis_id=batch.batch_analysis_id,
                    row_number=row.row_number,
                    uploaded_review_key=row.uploaded_review_key,
                    row_state=row_state,
                    review_id=review_id,
                    validation_errors=errors,
                ))

            if can_queue and candidate_model is not None and historic_graph_snapshot_id is not None:
                run = InferenceRun(
                    model_version_id=candidate_model.model_version_id,
                    provenance="real",
                    graph_snapshot_id=historic_graph_snapshot_id,
                    requested_by_user_id=user.user_id,
                    idempotency_key=idempotency_key,
                    threshold=candidate_model.recommended_threshold,
                    status="queued",
                    requested_count=accepted_count,
                    completed_count=0,
                )
                db.add(run)
                db.flush()
                batch.inference_run_id = run.inference_run_id
                job = InductiveInferenceJob(
                    inference_run_id=run.inference_run_id,
                    status="queued",
                    provenance="real",
                )
                db.add(job)
                db.flush()

            db.add(AuditLog(actor_user_id=user.user_id, action="batch_analysis.upload",
                            entity_type="batch_analysis", entity_key=str(batch.batch_analysis_id),
                            after_data={"row_count": len(rows), "accepted_count": accepted_count,
                                        "rejected_count": rejected_count, "status": status,
                                        "inference_run_id": batch.inference_run_id}))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "batch_import_conflict", "message": "The CSV conflicts with existing source records; no batch rows were committed."})
    return _batch_payload(batch, db=db)


@router.get("/batch-analyses")
def list_batch_analyses(
    limit: int = 25,
    offset: int = 0,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail={"code": "invalid_pagination", "message": "limit must be 1..100 and offset nonnegative."})
    total = db.scalar(select(func.count()).select_from(BatchAnalysis)) or 0
    batches = db.scalars(
        select(BatchAnalysis)
        .order_by(BatchAnalysis.batch_analysis_id.desc())
        .offset(offset).limit(limit)
    ).all()
    return {
        "items": [_batch_payload(b, db=db) for b in batches],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/batch-analyses/{batch_analysis_id}")
def get_batch_analysis(batch_analysis_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    batch = db.get(BatchAnalysis, batch_analysis_id)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_analysis_not_found", "message": "Batch analysis was not found."})
    _assert_can_read_batch(db, batch, user)
    payload = _batch_payload(batch, db=db)
    payload["scoring_available"] = (batch.status in ("queued", "running", "completed"))
    return payload


@router.get("/batch-analyses/{batch_analysis_id}/results")
def get_batch_analysis_results(
    batch_analysis_id: int,
    limit: int = 25,
    offset: int = 0,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail={"code": "invalid_pagination", "message": "limit must be 1..100 and offset nonnegative."})
    batch = db.get(BatchAnalysis, batch_analysis_id)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_analysis_not_found", "message": "Batch analysis was not found."})
    _assert_can_read_batch(db, batch, user)
    total = db.scalar(select(func.count()).select_from(BatchAnalysisRow).where(
        BatchAnalysisRow.batch_analysis_id == batch_analysis_id)) or 0
    rows = db.execute(
        select(BatchAnalysisRow, Review, FraudPrediction, InductivePredictionEvidence)
        .outerjoin(Review, Review.review_id == BatchAnalysisRow.review_id)
        .outerjoin(
            FraudPrediction,
            (FraudPrediction.inference_run_id == batch.inference_run_id)
            & (FraudPrediction.review_id == BatchAnalysisRow.review_id),
        )
        .outerjoin(
            InductivePredictionEvidence,
            InductivePredictionEvidence.fraud_prediction_id == FraudPrediction.fraud_prediction_id,
        )
        .where(BatchAnalysisRow.batch_analysis_id == batch_analysis_id)
        .order_by(BatchAnalysisRow.row_number)
        .offset(offset).limit(limit)
    ).all()

    items = []
    for row, review, pred, evidence in rows:
        pred_dict = None
        if pred is not None:
            pred_dict = {
                "fraud_prediction_id": pred.fraud_prediction_id,
                "risk_score": float(pred.risk_score),
                "predicted_label": pred.predicted_label,
                "decision": "flagged" if pred.predicted_label == 1 else "cleared",
                "attention_weights": pred.attention_weights,
                "graph_status": pred.graph_status,
                "evidence": {
                    "graph_snapshot_id": evidence.graph_snapshot_id,
                    "relation_schema_version": evidence.relation_schema_version,
                    "context_cutoff_at": evidence.context_cutoff_at.isoformat() if evidence.context_cutoff_at else None,
                    "neighbor_counts": evidence.neighbor_counts,
                    "historic_review_ids": evidence.historic_review_ids,
                    "stitched_graph_sha256": evidence.stitched_graph_sha256,
                    "input_feature_sha256": evidence.input_feature_sha256,
                    "embedding_sha256": evidence.embedding_sha256,
                    "bundle_manifest_sha256": evidence.bundle_manifest_sha256,
                } if evidence is not None else None,
            }
        items.append({
            "row_number": row.row_number,
            "row_state": row.row_state,
            "uploaded_review_key": row.uploaded_review_key,
            "validation_errors": row.validation_errors,
            "review": ({
                "review_id": review.review_id,
                "reviewer_id": review.reviewer_id,
                "product_id": review.product_id,
                "rating": review.rating,
                "reviewed_at": review.reviewed_at,
                "review_text": review.review_text,
            } if review is not None else None),
            "prediction": pred_dict,
        })
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "inference_run_id": batch.inference_run_id,
    }


@router.post("/batch-analyses/{batch_analysis_id}/score")
def score_batch_analysis(
    batch_analysis_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    batch = db.get(BatchAnalysis, batch_analysis_id)
    if batch is None:
        raise HTTPException(status_code=404, detail={"code": "batch_analysis_not_found", "message": "Batch analysis was not found."})
    _assert_can_read_batch(db, batch, user)

    if batch.status == "completed":
        return _batch_payload(batch, db=db)

    if batch.accepted_count == 0:
        raise HTTPException(status_code=422, detail={"code": "no_accepted_reviews", "message": "Batch has no accepted reviews to score."})

    if batch.historic_graph_snapshot_id is None:
        raise HTTPException(status_code=422, detail={"code": "historic_graph_snapshot_not_selected", "message": "No historic graph snapshot was selected for this batch."})

    snapshot = db.get(GraphSnapshot, batch.historic_graph_snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"code": "snapshot_not_found", "message": "Graph snapshot was not found."})
    if snapshot.storage_status != "available" or not snapshot.batch_context_permitted:
        raise HTTPException(status_code=409, detail={"code": "snapshot_not_permitted", "message": "Graph snapshot is not available or not permitted for batch context."})
    if snapshot.context_scope_key != "inductive-rur-rsr-rtr-v1" and snapshot.relation_schema_version != "inductive-rur-rsr-rtr-v1":
        raise HTTPException(status_code=409, detail={"code": "snapshot_scope_incompatible", "message": f"Graph snapshot scope '{snapshot.context_scope_key or snapshot.relation_schema_version}' is incompatible with model relation schema 'inductive-rur-rsr-rtr-v1'."})

    if batch.inference_run_id is None:
        candidate_model = db.scalar(
            select(ModelVersion)
            .join(PreprocessingVersion, PreprocessingVersion.preprocessing_version_id == ModelVersion.preprocessing_version_id)
            .where(
                ModelVersion.provenance == "real",
                ModelVersion.lifecycle_status == "verified",
                ModelVersion.supported_inference_mode == "inductive_batch_v1",
                ModelVersion.checkpoint_uri.is_not(None),
                ModelVersion.checkpoint_sha256.is_not(None),
                PreprocessingVersion.lifecycle_status == "verified",
            )
            .order_by(ModelVersion.model_version_id.desc())
            .limit(1)
        )
        if candidate_model is None:
            raise HTTPException(status_code=503, detail={"code": "verified_model_bundle_not_registered", "message": "No verified inductive model is registered."})

        run = InferenceRun(
            model_version_id=candidate_model.model_version_id,
            provenance="real",
            graph_snapshot_id=snapshot.graph_snapshot_id,
            requested_by_user_id=user.user_id,
            threshold=candidate_model.recommended_threshold,
            status="queued",
            requested_count=batch.accepted_count,
            completed_count=0,
        )
        db.add(run)
        db.flush()
        batch.inference_run_id = run.inference_run_id
        batch.status = "queued"
        job = InductiveInferenceJob(
            inference_run_id=run.inference_run_id,
            status="queued",
            provenance="real",
        )
        db.add(job)
        db.commit()
    else:
        job = db.scalar(select(InductiveInferenceJob).where(InductiveInferenceJob.inference_run_id == batch.inference_run_id))

    if job is None:
        job = InductiveInferenceJob(
            inference_run_id=batch.inference_run_id,
            status="queued",
            provenance="real",
        )
        db.add(job)
        db.commit()

    # Acquire lease
    now = datetime.now(timezone.utc)
    job.status = "running"
    job.worker_id = f"api-worker-{user.user_id}"
    job.lease_token = str(uuid.uuid4())
    job.lease_expires_at = now + timedelta(minutes=5)
    job.attempt_count += 1
    if job.started_at is None:
        job.started_at = now
    job.updated_at = now
    db.commit()

    from app.services.inductive_worker import process_inductive_job
    success = process_inductive_job(job.job_id, db)
    db.refresh(job)
    db.refresh(batch)

    if not success:
        error_code = job.last_error_code or "scoring_failed"
        error_msg = job.last_error or "Inductive scoring failed."
        if error_code == "snapshot_not_found":
            raise HTTPException(status_code=404, detail={"code": error_code, "message": error_msg})
        elif error_code in ("snapshot_not_permitted", "snapshot_scope_incompatible"):
            raise HTTPException(status_code=409, detail={"code": error_code, "message": error_msg})
        elif error_code in ("insufficient_historic_context", "no_accepted_reviews"):
            raise HTTPException(status_code=422, detail={"code": error_code, "message": error_msg})
        elif error_code == "bundle_verification_failed":
            raise HTTPException(status_code=503, detail={"code": error_code, "message": error_msg})
        else:
            raise HTTPException(status_code=500, detail={"code": error_code, "message": error_msg})

    return _batch_payload(batch, db=db)


@router.post("/batch-analyses/process-next")
def process_next_batch_job(
    worker_id: str = "manual-worker",
    actor: User = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    from app.services.inductive_worker import acquire_next_job, process_inductive_job
    job = acquire_next_job(db, worker_id=worker_id)
    if job is None:
        return {"processed": False, "message": "No eligible jobs in queue."}
    success = process_inductive_job(job.job_id, db)
    return {"processed": True, "job_id": job.job_id, "success": success}

