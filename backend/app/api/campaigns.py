"""Read-only analytics for explicitly synthetic review-bombing scenarios."""
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Integer, and_, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (Product, Review, Reviewer, SyntheticCampaign,
                        SyntheticCampaignMember, SyntheticCampaignReview, User)
from app.security import current_user
from app.services.neo4j_synthetic_projection import (Neo4jProjectionUnavailable,
                                                      read_synthetic_campaign_graph)

router = APIRouter(prefix="/api/v1/synthetic-campaigns", tags=["synthetic campaigns"])
SYNTHETIC_SOURCE = "synthetic_demo"


def _campaign(db: Session, campaign_key: str) -> SyntheticCampaign:
    campaign = db.scalar(select(SyntheticCampaign).where(
        SyntheticCampaign.campaign_key == campaign_key,
        SyntheticCampaign.provenance == SYNTHETIC_SOURCE,
    ))
    if campaign is None:
        raise HTTPException(status_code=404, detail={"code": "synthetic_campaign_not_found", "message": "Synthetic campaign was not found."})
    return campaign


def _validate_pagination(limit: int, offset: int) -> None:
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail={"code": "invalid_pagination", "message": "limit must be 1..100 and offset nonnegative."})


@router.get("/{campaign_key}/summary")
def campaign_summary(campaign_key: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_key)
    product = db.get(Product, campaign.product_id)
    attack = db.execute(
        select(func.count(Review.review_id), func.count(func.distinct(Review.reviewer_id)),
               func.avg(Review.rating), func.sum((Review.rating == 1).cast(Integer)),
               func.min(Review.reviewed_at), func.max(Review.reviewed_at))
        .join(SyntheticCampaignReview, SyntheticCampaignReview.review_id == Review.review_id)
        .where(SyntheticCampaignReview.synthetic_campaign_id == campaign.synthetic_campaign_id,
               SyntheticCampaignReview.campaign_period == "attack",
               SyntheticCampaignReview.provenance == SYNTHETIC_SOURCE,
               Review.source_system == SYNTHETIC_SOURCE)
    ).one()
    prior_count = db.scalar(
        select(func.count(Review.review_id))
        .join(SyntheticCampaignReview, SyntheticCampaignReview.review_id == Review.review_id)
        .where(SyntheticCampaignReview.synthetic_campaign_id == campaign.synthetic_campaign_id,
               SyntheticCampaignReview.campaign_period == "prior",
               SyntheticCampaignReview.provenance == SYNTHETIC_SOURCE,
               Review.source_system == SYNTHETIC_SOURCE)
    ) or 0
    member_count = db.scalar(select(func.count()).select_from(SyntheticCampaignMember).where(
        SyntheticCampaignMember.synthetic_campaign_id == campaign.synthetic_campaign_id,
        SyntheticCampaignMember.provenance == SYNTHETIC_SOURCE)) or 0
    overlap_count = 0
    prior_campaign = db.get(SyntheticCampaign, campaign.prior_campaign_id) if campaign.prior_campaign_id else None
    if prior_campaign and prior_campaign.provenance == SYNTHETIC_SOURCE:
        # Explicit self-join keeps both campaign scopes clear and uses only
        # persisted reviewer membership, never score/label data.
        current_member = SyntheticCampaignMember.__table__.alias("current_member")
        previous_member = SyntheticCampaignMember.__table__.alias("previous_member")
        overlap_count = db.scalar(select(func.count()).select_from(
            current_member.join(previous_member, current_member.c.reviewer_id == previous_member.c.reviewer_id)
        ).where(current_member.c.synthetic_campaign_id == campaign.synthetic_campaign_id,
                previous_member.c.synthetic_campaign_id == prior_campaign.synthetic_campaign_id,
                current_member.c.provenance == SYNTHETIC_SOURCE,
                previous_member.c.provenance == SYNTHETIC_SOURCE)) or 0

    attack_reviews = int(attack[0] or 0)
    review_days = (campaign.attack_end_at - campaign.attack_start_at).total_seconds() / 86400
    return {
        "campaign_key": campaign.campaign_key,
        "campaign_name": campaign.campaign_name,
        "provenance": campaign.provenance,
        "product": {"product_id": campaign.product_id, "name": product.display_name if product else None},
        "attack_window": {"start": campaign.attack_start_at, "end": campaign.attack_end_at},
        "comparison_window": {"start": campaign.prior_start_at, "end": campaign.prior_end_at},
        "attack_review_count": attack_reviews,
        "distinct_attack_reviewers": int(attack[1] or 0),
        "one_star_review_count": int(attack[3] or 0),
        "attack_mean_rating": float(attack[2]) if attack[2] is not None else None,
        "attack_reviews_per_day": round(attack_reviews / review_days, 3) if review_days > 0 else None,
        "first_attack_review_at": attack[4],
        "last_attack_review_at": attack[5],
        "comparison_review_count": int(prior_count),
        "campaign_member_count": int(member_count),
        "reviewers_overlapping_prior_campaign": int(overlap_count),
        "linked_prior_campaign_key": prior_campaign.campaign_key if prior_campaign else None,
        "description": campaign.description,
        "interpretation": "Synthetic scenario evidence only; not a model prediction or a finding about real reviewers.",
    }


@router.get("/{campaign_key}/rating-over-time")
def restaurant_rating_over_time(campaign_key: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_key)
    day = func.date(Review.reviewed_at).label("day")
    rows = db.execute(select(day, func.count(Review.review_id), func.avg(Review.rating))
                      .where(Review.product_id == campaign.product_id,
                             Review.source_system == SYNTHETIC_SOURCE,
                             Review.reviewed_at.is_not(None),
                             Review.reviewed_at <= campaign.attack_end_at)
                      .group_by(day).order_by(day)).all()
    return {"campaign_key": campaign.campaign_key, "provenance": SYNTHETIC_SOURCE,
            "items": [{"day": item_day if isinstance(item_day, date) else date.fromisoformat(str(item_day)), "review_count": int(count),
                       "observed_mean_rating": float(mean) if mean is not None else None}
                      for item_day, count, mean in rows]}


@router.get("/{campaign_key}/rating-comparison")
def observed_vs_scenario_adjusted_rating(campaign_key: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_key)
    filters = [Review.product_id == campaign.product_id,
               Review.source_system == SYNTHETIC_SOURCE,
               Review.reviewed_at >= campaign.attack_start_at,
               Review.reviewed_at <= campaign.attack_end_at,
               Review.rating.is_not(None)]
    observed = db.execute(select(func.count(Review.review_id), func.avg(Review.rating)).where(*filters)).one()
    attack_review_ids = select(SyntheticCampaignReview.review_id).where(
        SyntheticCampaignReview.synthetic_campaign_id == campaign.synthetic_campaign_id,
        SyntheticCampaignReview.campaign_period == "attack",
        SyntheticCampaignReview.provenance == SYNTHETIC_SOURCE,
    )
    adjusted = db.execute(select(func.count(Review.review_id), func.avg(Review.rating)).where(
        *filters, Review.review_id.not_in(attack_review_ids))).one()
    comparison = db.execute(select(func.count(Review.review_id), func.avg(Review.rating)).where(
        Review.product_id == campaign.product_id,
        Review.source_system == SYNTHETIC_SOURCE,
        Review.reviewed_at >= campaign.prior_start_at,
        Review.reviewed_at <= campaign.prior_end_at,
        Review.rating.is_not(None))).one()
    return {
        "campaign_key": campaign.campaign_key,
        "provenance": SYNTHETIC_SOURCE,
        "observed_attack_window": {"review_count": int(observed[0] or 0), "mean_rating": float(observed[1]) if observed[1] is not None else None},
        "scenario_adjusted_attack_window": {"review_count": int(adjusted[0] or 0), "mean_rating": float(adjusted[1]) if adjusted[1] is not None else None},
        "comparison_window": {"review_count": int(comparison[0] or 0), "mean_rating": float(comparison[1]) if comparison[1] is not None else None},
        "formula": "Scenario-adjusted mean = AVG(rating) for synthetic restaurant reviews in the attack window after excluding review IDs explicitly linked to this synthetic campaign. It is a scenario comparison, not a model risk adjustment.",
    }


@router.get("/{campaign_key}/volume-by-day")
def review_volume_by_day(campaign_key: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_key)
    day = func.date(Review.reviewed_at).label("day")
    rows = db.execute(select(day, func.count(Review.review_id), func.avg(Review.rating))
                      .where(Review.product_id == campaign.product_id,
                             Review.source_system == SYNTHETIC_SOURCE,
                             Review.reviewed_at >= campaign.prior_start_at,
                             Review.reviewed_at <= campaign.attack_end_at)
                      .group_by(day).order_by(day)).all()
    items = []
    for item_day, count, mean in rows:
        bucket_date = item_day if isinstance(item_day, date) else date.fromisoformat(str(item_day))
        period = "comparison" if campaign.prior_start_at.date() <= bucket_date <= campaign.prior_end_at.date() else (
            "attack" if campaign.attack_start_at.date() <= bucket_date <= campaign.attack_end_at.date() else "between_windows")
        items.append({"day": bucket_date, "period": period, "review_count": int(count),
                      "mean_rating": float(mean) if mean is not None else None})
    comparison_total = sum(row["review_count"] for row in items if row["period"] == "comparison")
    attack_total = sum(row["review_count"] for row in items if row["period"] == "attack")
    comparison_days = max(1, (campaign.prior_end_at.date() - campaign.prior_start_at.date()).days + 1)
    attack_days = max(1, (campaign.attack_end_at.date() - campaign.attack_start_at.date()).days + 1)
    return {"campaign_key": campaign.campaign_key, "provenance": SYNTHETIC_SOURCE,
            "comparison_review_count": comparison_total, "attack_review_count": attack_total,
            "comparison_reviews_per_day": round(comparison_total / comparison_days, 3),
            "attack_reviews_per_day": round(attack_total / attack_days, 3),
            "attack_to_comparison_daily_volume_ratio": round((attack_total / attack_days) / (comparison_total / comparison_days), 3) if comparison_total else None,
            "items": items}


@router.get("/{campaign_key}/members")
def campaign_members(campaign_key: str, limit: int = 25, offset: int = 0,
                     _: User = Depends(current_user), db: Session = Depends(get_db)):
    _validate_pagination(limit, offset)
    campaign = _campaign(db, campaign_key)
    members_query = select(SyntheticCampaignMember, Reviewer).join(
        Reviewer, Reviewer.reviewer_id == SyntheticCampaignMember.reviewer_id
    ).where(SyntheticCampaignMember.synthetic_campaign_id == campaign.synthetic_campaign_id,
            SyntheticCampaignMember.provenance == SYNTHETIC_SOURCE,
            Reviewer.source_system == SYNTHETIC_SOURCE)
    total = db.scalar(select(func.count()).select_from(members_query.subquery())) or 0
    members = db.execute(members_query.order_by(Reviewer.external_reviewer_key).offset(offset).limit(limit)).all()
    reviewer_ids = [reviewer.reviewer_id for _, reviewer in members]
    attack_rows = db.execute(select(SyntheticCampaignReview, Review).join(
        Review, Review.review_id == SyntheticCampaignReview.review_id
    ).where(SyntheticCampaignReview.synthetic_campaign_id == campaign.synthetic_campaign_id,
            SyntheticCampaignReview.campaign_period == "attack",
            SyntheticCampaignReview.provenance == SYNTHETIC_SOURCE,
            Review.reviewer_id.in_(reviewer_ids) if reviewer_ids else False,
            Review.source_system == SYNTHETIC_SOURCE).order_by(Review.reviewed_at)).all()
    previous_rows = []
    if campaign.prior_campaign_id and reviewer_ids:
        previous_rows = db.execute(select(SyntheticCampaignReview, Review).join(
            Review, Review.review_id == SyntheticCampaignReview.review_id
        ).where(SyntheticCampaignReview.synthetic_campaign_id == campaign.prior_campaign_id,
                SyntheticCampaignReview.provenance == SYNTHETIC_SOURCE,
                Review.reviewer_id.in_(reviewer_ids), Review.source_system == SYNTHETIC_SOURCE)
            .order_by(Review.reviewed_at)).all()
    attacks_by_reviewer: dict[int, list] = defaultdict(list)
    previous_by_reviewer: dict[int, list] = defaultdict(list)
    for link, review in attack_rows:
        attacks_by_reviewer[review.reviewer_id].append((link, review))
    for link, review in previous_rows:
        previous_by_reviewer[review.reviewer_id].append((link, review))
    items = []
    for member, reviewer in members:
        attacks = attacks_by_reviewer[reviewer.reviewer_id]
        previous = previous_by_reviewer[reviewer.reviewer_id]
        items.append({
            "reviewer_id": reviewer.reviewer_id,
            "external_reviewer_key": reviewer.external_reviewer_key,
            "membership_type": member.membership_type,
            "provenance": member.provenance,
            "evidence": {
                "attack_review_count": len(attacks),
                "attack_one_star_count": sum(1 for _, row in attacks if row.rating == 1),
                "attack_review_keys": [row.source_review_key for _, row in attacks],
                "attack_review_times": [row.reviewed_at for _, row in attacks],
                "attack_review_ratings": [row.rating for _, row in attacks],
                "attack_product_ids": [row.product_id for _, row in attacks],
                "attack_review_texts": [row.review_text for _, row in attacks],
                "overlapped_prior_campaign": bool(previous),
                "prior_review_count": len(previous),
                "prior_review_keys": [row.source_review_key for _, row in previous],
                "prior_review_times": [row.reviewed_at for _, row in previous],
                "prior_review_ratings": [row.rating for _, row in previous],
                "evidence_notes": [link.evidence_note for link, _ in attacks + previous],
                "source": "stored synthetic_demo campaign membership and review fields; no model score or attention used",
            },
        })
    return {"campaign_key": campaign.campaign_key, "provenance": SYNTHETIC_SOURCE,
            "items": items, "total": int(total), "limit": limit, "offset": offset}


@router.get("/{campaign_key}/graph")
def synthetic_campaign_graph(campaign_key: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = _campaign(db, campaign_key)
    try:
        payload = read_synthetic_campaign_graph(campaign.campaign_key)
    except Neo4jProjectionUnavailable as exc:
        raise HTTPException(status_code=503, detail={
            "code": "neo4j_unavailable",
            "message": str(exc),
            "provenance": SYNTHETIC_SOURCE,
        }) from exc
    if not any("Campaign" in row.get("labels", []) and row.get("campaign_key") == campaign.campaign_key
               for row in payload["nodes"]):
        raise HTTPException(status_code=409, detail={
            "code": "campaign_graph_not_projected",
            "message": "This synthetic campaign has not been projected to Neo4j yet.",
            "provenance": SYNTHETIC_SOURCE,
        })
    return payload
