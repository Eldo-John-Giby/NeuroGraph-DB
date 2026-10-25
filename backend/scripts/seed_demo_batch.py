"""Seed a deterministic, explicitly synthetic restaurant review-bombing scenario.

This creates review/campaign evidence only. It does not create model outputs,
attention values, labels, checkpoint artifacts, or a verified model. Run only
after applying Alembic migrations and with DEMO_MODE=true.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if os.environ.get("DEMO_MODE", "").strip().lower() != "true":
    raise SystemExit("Refusing to seed demo data: set DEMO_MODE=true explicitly.")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select

from app.db import make_session_factory
from app.models import (BatchAnalysis, BatchAnalysisRow, FraudPrediction, GraphSnapshot,
                        GraphSnapshotReview, GraphSyncJob, InferenceRun, ModelVersion,
                        PreprocessingVersion, Product, Review, ReviewFeedback, Reviewer,
                        SyntheticCampaign, SyntheticCampaignMember,
                        SyntheticCampaignReview)

SEED = 42
SOURCE = "synthetic_demo"
ATTACK_KEY = "harbor-table-review-bombing-seed-42"
PRIOR_KEY = "cedar-spoon-prior-campaign-seed-42"
LEGACY_RUN_KEY = "98ec3c6d-fa9a-5af7-b492-2b2d3e8240c7"  # former generic seed, seed 42
DEMO_TZ = timezone.utc
BASELINE_START = datetime(2025, 4, 2, 9, tzinfo=DEMO_TZ)
BASELINE_END = datetime(2025, 4, 8, 21, tzinfo=DEMO_TZ)
PRIOR_START = datetime(2025, 4, 2, 10, tzinfo=DEMO_TZ)
PRIOR_END = datetime(2025, 4, 2, 22, tzinfo=DEMO_TZ)
ATTACK_START = datetime(2025, 4, 10, 8, tzinfo=DEMO_TZ)
ATTACK_END = datetime(2025, 4, 11, 20, tzinfo=DEMO_TZ)
SEED_CREATED_AT = datetime(2025, 4, 12, tzinfo=timezone.utc)


def _review_text(kind: str, index: int, rating: int) -> str:
    if kind == "attack":
        shared = ("Food was cold, service was slow, and we will not return." if index % 2 == 0
                  else "The meal arrived cold; service was slow and I would not return.")
        detail = ("Our table waited a long time." if index % 3 == 0 else
                  "The visit felt poorly handled." if index % 3 == 1 else
                  "The experience was below expectations.")
        return f"{shared} {detail} Visit note {index + 1:02d}."
    if kind == "prior":
        return ("The food was cold and the service was slow. "
                f"Earlier campaign visit {index + 1:02d}; rating {rating}.")
    descriptions = (
        "The staff were welcoming and the room was comfortable.",
        "Dinner arrived on time and the portions were generous.",
        "A pleasant meal with attentive service.",
        "The menu had good options and the visit went smoothly.",
    )
    return f"{descriptions[index % len(descriptions)]} Table visit {index + 1:02d}."


def _same_instant(left: datetime, right: datetime) -> bool:
    # SQLite drops timezone metadata on round trip; PostgreSQL preserves it.
    if left.tzinfo is None:
        left = left.replace(tzinfo=DEMO_TZ)
    return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)


def _cleanup_legacy_generic_seed(db) -> int:
    """Remove only rows identified by the former deterministic seed keys."""
    retained_for_graph_jobs = 0
    legacy_run = db.scalar(select(InferenceRun).where(InferenceRun.run_key == LEGACY_RUN_KEY))
    legacy_reviews = list(db.scalars(select(Review).where(
        Review.source_system == SOURCE,
        Review.source_review_key.like("demo-review-%"),
    )))
    legacy_ids = [row.review_id for row in legacy_reviews]
    if legacy_run:
        run_model = db.get(ModelVersion, legacy_run.model_version_id)
        run_review_ids = set(db.scalars(select(FraudPrediction.review_id).where(
            FraudPrediction.inference_run_id == legacy_run.inference_run_id)))
        if (run_model is None or run_model.provenance != SOURCE or
                not run_review_ids.issubset(set(legacy_ids))):
            raise RuntimeError("Former generic seed run has unexpected provenance or review references; refusing cleanup.")
        db.execute(delete(FraudPrediction).where(FraudPrediction.inference_run_id == legacy_run.inference_run_id))
        db.delete(legacy_run)
        db.flush()
    if legacy_ids:
        # Keep unrelated imports and feedback intact; fail with a clear reason
        # rather than cascade-delete records outside the old seed's ownership.
        references = [
            db.scalar(select(func.count()).select_from(BatchAnalysisRow).where(BatchAnalysisRow.review_id.in_(legacy_ids))) or 0,
            db.scalar(select(func.count()).select_from(ReviewFeedback).where(ReviewFeedback.review_id.in_(legacy_ids))) or 0,
            db.scalar(select(func.count()).select_from(SyntheticCampaignReview).where(SyntheticCampaignReview.review_id.in_(legacy_ids))) or 0,
        ]
        remaining_predictions = db.scalar(select(func.count()).select_from(FraudPrediction).where(
            FraudPrediction.review_id.in_(legacy_ids))) or 0
        if any(references) or remaining_predictions:
            raise RuntimeError("Legacy demo review rows have non-seed references; refusing to delete them automatically.")
        db.execute(delete(GraphSnapshotReview).where(GraphSnapshotReview.review_id.in_(legacy_ids)))
        # Graph sync jobs are durable operational history and have a restrictive
        # FK to their source review. Keep those referenced legacy rows intact;
        # the restaurant scenario uses distinct source keys and is independent.
        linked_review_ids = set(db.scalars(select(GraphSyncJob.review_id).where(
            GraphSyncJob.review_id.in_(legacy_ids), GraphSyncJob.review_id.is_not(None)
        )))
        retained_for_graph_jobs = len(linked_review_ids)
        deletable_review_ids = set(legacy_ids) - linked_review_ids
        if deletable_review_ids:
            db.execute(delete(Review).where(Review.review_id.in_(deletable_review_ids)))

    legacy_model = db.scalar(select(ModelVersion).where(ModelVersion.version_key == "demo-synthetic-v0"))
    if legacy_model and legacy_model.provenance == SOURCE:
        remaining_runs = db.scalar(select(func.count()).select_from(InferenceRun).where(
            InferenceRun.model_version_id == legacy_model.model_version_id)) or 0
        if remaining_runs == 0:
            prep_id = legacy_model.preprocessing_version_id
            db.delete(legacy_model)
            db.flush()
            prep = db.get(PreprocessingVersion, prep_id)
            if prep and (db.scalar(select(func.count()).select_from(ModelVersion).where(
                    ModelVersion.preprocessing_version_id == prep_id)) or 0) == 0:
                db.delete(prep)

    legacy_snapshot = db.scalar(select(GraphSnapshot).where(
        GraphSnapshot.snapshot_key == "demo-synthetic-graph-v0-seed-42"))
    if legacy_snapshot:
        run_refs = db.scalar(select(func.count()).select_from(InferenceRun).where(
            InferenceRun.graph_snapshot_id == legacy_snapshot.graph_snapshot_id)) or 0
        batch_refs = db.scalar(select(func.count()).select_from(BatchAnalysis).where(
            BatchAnalysis.historic_graph_snapshot_id == legacy_snapshot.graph_snapshot_id)) or 0
        graph_job_refs = db.scalar(select(func.count()).select_from(GraphSyncJob).where(
            GraphSyncJob.graph_snapshot_id == legacy_snapshot.graph_snapshot_id)) or 0
        if run_refs == 0 and batch_refs == 0 and graph_job_refs == 0:
            db.execute(delete(GraphSnapshotReview).where(GraphSnapshotReview.graph_snapshot_id == legacy_snapshot.graph_snapshot_id))
            db.delete(legacy_snapshot)

    # Delete former demo authors/products only if no remaining reviews depend on them.
    for reviewer in list(db.scalars(select(Reviewer).where(
        Reviewer.source_system == SOURCE, Reviewer.external_reviewer_key.like("demo-reviewer-%")
    ))):
        if (db.scalar(select(func.count()).select_from(Review).where(Review.reviewer_id == reviewer.reviewer_id)) or 0) == 0:
            db.delete(reviewer)
    for product in list(db.scalars(select(Product).where(
        Product.source_system == SOURCE, Product.external_product_key.like("demo-product-%")
    ))):
        if (db.scalar(select(func.count()).select_from(Review).where(Review.product_id == product.product_id)) or 0) == 0:
            db.delete(product)
    return retained_for_graph_jobs


def _get_or_create_reviewer(db, key: str) -> Reviewer:
    row = db.scalar(select(Reviewer).where(Reviewer.source_system == SOURCE,
                                         Reviewer.external_reviewer_key == key))
    if row is None:
        row = Reviewer(source_system=SOURCE, external_reviewer_key=key, created_at=SEED_CREATED_AT)
        db.add(row)
        db.flush()
    return row


def _get_or_create_product(db, key: str, name: str) -> Product:
    row = db.scalar(select(Product).where(Product.source_system == SOURCE,
                                         Product.external_product_key == key))
    if row is None:
        row = Product(source_system=SOURCE, external_product_key=key, display_name=name, created_at=SEED_CREATED_AT)
        db.add(row)
        db.flush()
    elif row.display_name != name:
        raise RuntimeError(f"Existing synthetic product {key!r} has a conflicting display name.")
    return row


def seed() -> dict[str, object]:
    session_factory = make_session_factory()
    with session_factory.begin() as db:
        existing_attack = db.scalar(select(SyntheticCampaign).where(SyntheticCampaign.campaign_key == ATTACK_KEY))
        existing_prior = db.scalar(select(SyntheticCampaign).where(SyntheticCampaign.campaign_key == PRIOR_KEY))
        if existing_attack or existing_prior:
            if not (existing_attack and existing_prior):
                raise RuntimeError("A partial restaurant scenario exists; refusing to silently complete it.")
            attack_count = db.scalar(select(func.count()).select_from(SyntheticCampaignReview).where(
                SyntheticCampaignReview.synthetic_campaign_id == existing_attack.synthetic_campaign_id,
                SyntheticCampaignReview.campaign_period == "attack")) or 0
            if (existing_attack.provenance != SOURCE or existing_prior.provenance != SOURCE or
                    attack_count != 36 or not _same_instant(existing_attack.attack_start_at, ATTACK_START)):
                raise RuntimeError("Existing restaurant scenario conflicts with the deterministic seed manifest.")
            return {"campaign_key": ATTACK_KEY, "prior_campaign_key": PRIOR_KEY,
                    "attack_review_count": attack_count, "seed": SEED,
                    "provenance": SOURCE, "already_seeded": True}

        retained_legacy_reviews = _cleanup_legacy_generic_seed(db)
        target = _get_or_create_product(db, "restaurant-harbor-table", "Harbor Table · synthetic restaurant")
        previous = _get_or_create_product(db, "restaurant-cedar-spoon", "Cedar Spoon · synthetic restaurant")
        reviewers = {f"campaign-reviewer-{index:02d}": _get_or_create_reviewer(db, f"campaign-reviewer-{index:02d}")
                     for index in range(1, 57)}

        # Prior suspicious burst: 8 reviewers later overlap the target attack,
        # with 4 additional accounts participating only in this earlier burst.
        prior_campaign = SyntheticCampaign(
            campaign_key=PRIOR_KEY,
            campaign_name="Cedar Spoon prior review burst (synthetic)",
            product_id=previous.product_id,
            prior_start_at=datetime(2025, 3, 20, tzinfo=DEMO_TZ),
            prior_end_at=datetime(2025, 3, 27, tzinfo=DEMO_TZ),
            attack_start_at=PRIOR_START,
            attack_end_at=PRIOR_END,
            description="A compact earlier one-star burst used only to demonstrate reviewer overlap with the later Harbor Table campaign.",
            provenance=SOURCE, created_at=SEED_CREATED_AT,
        )
        db.add(prior_campaign)
        db.flush()
        prior_reviewer_keys = ([f"campaign-reviewer-{index:02d}" for index in range(1, 9)] +
                               [f"campaign-reviewer-{index:02d}" for index in range(25, 29)])
        for index in range(15):
            rating = 1 if index < 13 else 2
            reviewer_key = prior_reviewer_keys[index % len(prior_reviewer_keys)]
            review = Review(
                source_system=SOURCE, source_review_key=f"cedar-prior-{index + 1:03d}",
                reviewer_id=reviewers[reviewer_key].reviewer_id, product_id=previous.product_id,
                rating=rating, reviewed_at=PRIOR_START + timedelta(minutes=45 * index),
                review_text=_review_text("prior", index, rating), created_at=SEED_CREATED_AT,
                updated_at=SEED_CREATED_AT,
            )
            db.add(review); db.flush()
            db.add(SyntheticCampaignReview(synthetic_campaign_id=prior_campaign.synthetic_campaign_id,
                                           review_id=review.review_id, campaign_period="attack",
                                           evidence_note="Part of the earlier concentrated synthetic review burst.", provenance=SOURCE))
        for key in prior_reviewer_keys:
            db.add(SyntheticCampaignMember(synthetic_campaign_id=prior_campaign.synthetic_campaign_id,
                                           reviewer_id=reviewers[key].reviewer_id,
                                           membership_type="prior_participant", provenance=SOURCE))

        # Main restaurant campaign has a fixed comparison window, followed by
        # 36 reviews from 24 connected accounts in a 36-hour burst.
        attack_campaign = SyntheticCampaign(
            campaign_key=ATTACK_KEY,
            campaign_name="Harbor Table concentrated low-rating campaign (synthetic)",
            product_id=target.product_id,
            prior_campaign_id=prior_campaign.synthetic_campaign_id,
            prior_start_at=BASELINE_START,
            prior_end_at=BASELINE_END,
            attack_start_at=ATTACK_START,
            attack_end_at=ATTACK_END,
            description="Synthetic restaurant review-bombing scenario: concentrated low ratings, repeated reviewer accounts, shared wording, and overlap with an earlier campaign.",
            provenance=SOURCE, created_at=SEED_CREATED_AT,
        )
        db.add(attack_campaign)
        db.flush()

        # Baseline target restaurant traffic: 28 reviews spread over six days.
        for index in range(28):
            reviewer_key = f"campaign-reviewer-{29 + index:02d}"
            rating = (4, 5, 4, 3, 5, 4, 4)[index % 7]
            when = BASELINE_START + timedelta(hours=(index * 5) % 140)
            review = Review(
                source_system=SOURCE, source_review_key=f"harbor-baseline-{index + 1:03d}",
                reviewer_id=reviewers[reviewer_key].reviewer_id, product_id=target.product_id,
                rating=rating, reviewed_at=when, review_text=_review_text("baseline", index, rating),
                created_at=SEED_CREATED_AT, updated_at=SEED_CREATED_AT,
            )
            db.add(review); db.flush()
            db.add(SyntheticCampaignReview(synthetic_campaign_id=attack_campaign.synthetic_campaign_id,
                                           review_id=review.review_id, campaign_period="prior",
                                           evidence_note="Comparison-window restaurant review outside the attack burst.", provenance=SOURCE))

        attack_reviewer_keys = [f"campaign-reviewer-{index:02d}" for index in range(1, 25)]
        for index, reviewer_key in enumerate(attack_reviewer_keys):
            db.add(SyntheticCampaignMember(synthetic_campaign_id=attack_campaign.synthetic_campaign_id,
                                           reviewer_id=reviewers[reviewer_key].reviewer_id,
                                           membership_type="attack_participant", provenance=SOURCE))
        for index in range(36):
            rating = 1 if index < 30 else 2
            reviewer_key = attack_reviewer_keys[index % len(attack_reviewer_keys)]
            when = ATTACK_START + timedelta(minutes=59 * index)
            review = Review(
                source_system=SOURCE, source_review_key=f"harbor-attack-{index + 1:03d}",
                reviewer_id=reviewers[reviewer_key].reviewer_id, product_id=target.product_id,
                rating=rating, reviewed_at=when, review_text=_review_text("attack", index, rating),
                created_at=SEED_CREATED_AT, updated_at=SEED_CREATED_AT,
            )
            db.add(review); db.flush()
            db.add(SyntheticCampaignReview(synthetic_campaign_id=attack_campaign.synthetic_campaign_id,
                                           review_id=review.review_id, campaign_period="attack",
                                           evidence_note="Synthetic attack-window review; inspect the stored timestamp, rating, reviewer, and shared wording.", provenance=SOURCE))
        db.flush()

        return {
            "campaign_key": ATTACK_KEY,
            "prior_campaign_key": PRIOR_KEY,
            "seed": SEED,
            "target_product_key": "restaurant-harbor-table",
            "attack_review_count": 36,
            "attack_reviewer_count": 24,
            "one_star_attack_count": 30,
            "prior_overlap_count": 8,
            "comparison_review_count": 28,
            "provenance": SOURCE,
            "scores_created": 0,
            "attention_values_created": 0,
            "legacy_reviews_retained_for_graph_sync": retained_legacy_reviews,
            "already_seeded": False,
        }


def main() -> None:
    result = seed()
    print(json.dumps(result, sort_keys=True))
    print("Synthetic scenario records only: no ML scores, attention, ground-truth labels, or verified model were created.")


if __name__ == "__main__":
    main()
