"""Label-free relation construction for uploaded reviews.

Node order is uploaded reviews first, followed by permitted historical reviews.
Only edges touching an uploaded node are returned; historic-to-historic edges
remain those of the selected immutable snapshot.
The relation schema is intentionally versioned and is not claimed checkpoint-
compatible until a real model manifest names this exact implementation.
"""
from collections import defaultdict
from datetime import timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GraphSnapshot, GraphSnapshotReview, Review
from app.services.batch_csv import BatchReviewInput, PermittedHistoricContext, RelationEdges


class LabelFreeBatchRelationBuilder:
    relation_schema_version = "batch-rur-rsr-rtr-v1"

    def __init__(self, *, max_time_gap: timedelta = timedelta(days=30), max_neighbors: int = 50):
        if max_time_gap <= timedelta(0):
            raise ValueError("max_time_gap must be positive")
        if max_neighbors < 1:
            raise ValueError("max_neighbors must be positive")
        self.max_time_gap = max_time_gap
        self.max_neighbors = max_neighbors

    def build(self, uploaded_reviews: Sequence[BatchReviewInput], *,
              historic_context: PermittedHistoricContext) -> RelationEdges:
        if historic_context.split not in {"train", "validation", "test"}:
            raise ValueError("historic context must name an explicit graph split")
        if len({r.review_id for r in uploaded_reviews}) != len(uploaded_reviews):
            raise ValueError("uploaded review ids must be unique")
        uploaded_ids = {r.review_id for r in uploaded_reviews}
        if uploaded_ids.intersection(r.review_id for r in historic_context.reviews):
            raise ValueError("uploaded and historic review ids must be disjoint")

        nodes = [*uploaded_reviews, *historic_context.reviews]
        uploaded_count = len(uploaded_reviews)

        def matching_edges(key_fn, distance_fn=None) -> set[tuple[int, int]]:
            groups: dict[object, list[int]] = defaultdict(list)
            for index, review in enumerate(nodes):
                groups[key_fn(review)].append(index)
            edges: set[tuple[int, int]] = set()
            for left in range(uploaded_count):
                candidates = [right for right in groups[key_fn(nodes[left])] if right != left]
                if distance_fn is not None:
                    candidates.sort(key=lambda right: (distance_fn(nodes[left], nodes[right]), nodes[right].review_id))
                else:
                    candidates.sort(key=lambda right: (nodes[right].reviewed_at, nodes[right].review_id))
                for right in candidates[:self.max_neighbors]:
                    if left < uploaded_count or right < uploaded_count:
                        edges.add((left, right))
                        edges.add((right, left))
            return edges

        rur = matching_edges(lambda review: review.reviewer_id)
        rsr = matching_edges(lambda review: (review.product_id, review.rating))
        rtr = matching_edges(
            lambda review: review.product_id,
            lambda left, right: abs(left.reviewed_at - right.reviewed_at),
        )
        rtr = {edge for edge in rtr if abs(nodes[edge[0]].reviewed_at - nodes[edge[1]].reviewed_at) <= self.max_time_gap}
        return RelationEdges(tuple(sorted(rur)), tuple(sorted(rsr)), tuple(sorted(rtr)),
                             self.relation_schema_version)


def load_permitted_historic_context(db: Session, snapshot_id: int, *, split: str) -> PermittedHistoricContext:
    """Load only relation inputs from explicitly permitted snapshot membership.

    The SQL projection deliberately omits Review.ground_truth_label and
    Review.label_source. `split` is the graph partition, not the target label.
    """
    if split not in {"train", "validation", "test"}:
        raise ValueError("split must be explicit")
    snapshot = db.get(GraphSnapshot, snapshot_id)
    if snapshot is None or snapshot.storage_status != "available" or not snapshot.batch_context_permitted:
        raise ValueError("historic graph snapshot is unavailable or not permitted")
    rows = db.execute(
        select(Review.review_id, Review.reviewer_id, Review.product_id,
               Review.rating, Review.reviewed_at, Review.review_text)
        .join(GraphSnapshotReview, GraphSnapshotReview.review_id == Review.review_id)
        .where(GraphSnapshotReview.graph_snapshot_id == snapshot_id,
               GraphSnapshotReview.split == split,
               Review.reviewer_id.is_not(None), Review.product_id.is_not(None),
               Review.rating.is_not(None), Review.reviewed_at.is_not(None),
               Review.review_text.is_not(None))
    ).all()
    history = []
    for r in rows:
        reviewed_at = r.reviewed_at
        if reviewed_at.tzinfo is None:
            reviewed_at = reviewed_at.replace(tzinfo=timezone.utc)
        history.append(BatchReviewInput(int(r.review_id), int(r.reviewer_id), int(r.product_id),
                                        int(r.rating), reviewed_at, r.review_text))
    return PermittedHistoricContext(snapshot_id, split, history)
