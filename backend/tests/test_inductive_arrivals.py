"""Verify live within-upload stitching against the actual training graph builder."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.services.batch_csv import BatchReviewInput
from app.services.inductive_relations import stitch_arrivals
from ml.build_yelpchi_inductive_graph import build_inductive_edges


def test_live_arrival_edges_match_training_builder_and_neighbor_cap():
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    records = [BatchReviewInput(index + 1, index % 4, index % 2, 1 if index % 3 else 5,
                               start + timedelta(hours=index), 'Unlabelled review', f'r-{index:03d}') for index in range(140)]
    frame = pd.DataFrame([{'node_index': index, 'reviewer_id': row.reviewer_id,
                           'product_id': row.product_id, 'rating': row.rating,
                           'date': row.reviewed_at} for index, row in enumerate(records)])
    reference = build_inductive_edges(frame, max_neighbors=50)
    pairs, _ = stitch_arrivals(records[:10], records[10:], max_neighbors=50)
    for relation in pairs:
        expected = reference[relation]
        expected = expected[:, expected[1] >= 10]
        # Training groups edges by identity; live stitching groups them by target.
        # Compare the exact directed multiset, independent of storage order.
        assert sorted(pairs[relation]) == sorted(zip(expected[0].tolist(), expected[1].tolist()))
        assert all(source < target for source, target in pairs[relation])
        assert max(np.bincount([target for _, target in pairs[relation]])) <= 50


def test_later_uploaded_review_gets_prior_peer_context_without_snapshot_mutation():
    start = datetime(2026, 10, 20, tzinfo=timezone.utc)
    rows = [BatchReviewInput(index + 1, index + 1, 9, 1,
                            start + timedelta(minutes=index), 'Repeated negative text') for index in range(3)]
    history = []
    pairs, neighbors = stitch_arrivals(history, rows)
    assert pairs['rur'] == []
    assert pairs['rsr'] == [(0, 1), (0, 2), (1, 2)]
    assert neighbors[3]['rsr'] == [1, 2]
    assert history == []
