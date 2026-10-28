"""Past-to-arrival relations shared by live inference and graph evidence.

Earlier uploaded records participate as context exactly as earlier arrivals do
in build_yelpchi_inductive_graph.py. No labels or model decisions are inputs.
"""
from collections import defaultdict
from datetime import timedelta
from typing import Sequence

from app.services.batch_csv import BatchReviewInput


def node_order(review: BatchReviewInput):
    return review.reviewed_at, review.source_review_key or str(review.review_id)


def stitch_arrivals(history: Sequence[BatchReviewInput], arrivals: Sequence[BatchReviewInput], max_neighbors: int = 50):
    if max_neighbors < 1:
        raise ValueError('max_neighbors must be positive')
    nodes = [*history, *arrivals]
    by_user, by_rating, by_product = defaultdict(list), defaultdict(list), defaultdict(list)
    pairs = {name: [] for name in ('rur', 'rsr', 'rtr')}
    neighbors = {}

    def add(index, review):
        by_user[review.reviewer_id].append(index)
        by_rating[(review.product_id, review.rating)].append(index)
        by_product[review.product_id].append(index)

    for index, review in enumerate(history):
        add(index, review)
    for relative, review in enumerate(arrivals):
        target = len(history) + relative
        # Each lookup contains only history and arrivals preceding this target.
        recent_product = by_product[review.product_id][-max_neighbors:]
        selected = {
            'rur': by_user[review.reviewer_id][-max_neighbors:],
            'rsr': by_rating[(review.product_id, review.rating)][-max_neighbors:],
            'rtr': [index for index in reversed(recent_product)
                    if timedelta(0) <= review.reviewed_at - nodes[index].reviewed_at <= timedelta(days=30)],
        }
        neighbors[review.review_id] = {}
        for relation, sources in selected.items():
            if any(nodes[index].reviewed_at > review.reviewed_at for index in sources):
                raise ValueError('Future context cannot be stitched to an arrival')
            pairs[relation].extend((index, target) for index in sources)
            neighbors[review.review_id][relation] = [nodes[index].review_id for index in sources]
        add(target, review)
    return pairs, neighbors
