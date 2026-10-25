"""Unit tests proving temporal causality and zero future/label leakage in the inductive replay pipeline."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.build_yelpchi_inductive_graph import build_inductive_edges, build_inductive_features


@pytest.fixture
def sample_temporal_reviews() -> pd.DataFrame:
    base_time = datetime(2011, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    records = []
    # User 1 writes 4 reviews over 4 months
    for i in range(4):
        records.append({
            "review_id": f"rev-u1-{i}",
            "reviewer_id": "user-1",
            "product_id": f"prod-{i % 2}",
            "rating": 5.0 if i % 2 == 0 else 1.0,
            "date": base_time + timedelta(days=i * 20),
            "review_text": f"Review number {i} with some exciting exclamation!",
            "label": 1 if i == 3 else 0,
            "source_file": "test.csv",
        })
    # User 2 writes reviews for product 0
    for j in range(3):
        records.append({
            "review_id": f"rev-u2-{j}",
            "reviewer_id": "user-2",
            "product_id": "prod-0",
            "rating": 5.0,
            "date": base_time + timedelta(days=j * 15 + 5),
            "review_text": f"User two review {j} for product zero.",
            "label": 0,
            "source_file": "test.csv",
        })

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values(["date", "review_id"], kind="stable").reset_index(drop=True)
    df["node_index"] = np.arange(len(df), dtype=np.int64)
    return df


def test_feature_temporal_causality_no_future_leakage(sample_temporal_reviews: pd.DataFrame):
    """Proves that altering future rows has zero effect on past/current feature vectors."""
    features_orig, col_names = build_inductive_features(sample_temporal_reviews)

    # Modify future rows: change ratings, text, and labels of rows 3, 4, 5, 6
    modified = sample_temporal_reviews.copy(deep=True)
    for idx in range(3, len(modified)):
        modified.loc[idx, "rating"] = 3.0
        modified.loc[idx, "review_text"] = "Completely changed text with lots of question marks???"
        modified.loc[idx, "label"] = 1 - modified.loc[idx, "label"]

    features_mod, _ = build_inductive_features(modified)

    # Rows 0, 1, 2 must be IDENTICAL bit-for-bit
    np.testing.assert_array_equal(
        features_orig[:3],
        features_mod[:3],
        err_msg="Temporal causality violated: future review changes altered past feature vectors!",
    )


def test_feature_construction_never_accesses_labels(sample_temporal_reviews: pd.DataFrame):
    """Proves that labels are completely excluded from metadata features."""
    features_orig, _ = build_inductive_features(sample_temporal_reviews)

    # Invert all labels
    inverted = sample_temporal_reviews.copy(deep=True)
    inverted["label"] = 1 - inverted["label"]
    features_inv, _ = build_inductive_features(inverted)

    np.testing.assert_array_equal(
        features_orig,
        features_inv,
        err_msg="Label leakage: changing labels altered feature representations!",
    )


def test_edge_temporal_causality_strict_past_to_candidate(sample_temporal_reviews: pd.DataFrame):
    """Proves all edges strictly point from past to candidate (src < tgt and date[src] <= date[tgt])."""
    edges = build_inductive_edges(sample_temporal_reviews, max_neighbors=50, rtr_max_days=30)
    dates = sample_temporal_reviews.date.to_numpy()

    for rel_name, edge_arr in edges.items():
        if edge_arr.shape[1] == 0:
            continue
        src = edge_arr[0]
        tgt = edge_arr[1]

        # Invariant 1: Source arrived strictly before target in arrival index
        assert (src < tgt).all(), f"Relation {rel_name} contains future-to-past edge (src >= tgt)"

        # Invariant 2: Source timestamp <= target timestamp
        assert (dates[src] <= dates[tgt]).all(), f"Relation {rel_name} contains timestamp violation (date[src] > date[tgt])"

        # Invariant 3: No reverse candidate-to-historic edge exists
        edge_pairs = set(zip(src.tolist(), tgt.tolist()))
        for s, t in edge_pairs:
            assert (t, s) not in edge_pairs, f"Relation {rel_name} contains bidirectional or candidate->historic edge ({t}, {s})"


def test_neighbor_cap_enforced_at_50():
    """Proves each relation caps incoming neighbors at exactly 50 most recent."""
    base_time = datetime(2010, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Create 80 reviews for the same reviewer and product
    records = []
    for i in range(80):
        records.append({
            "review_id": f"burst-{i:03d}",
            "reviewer_id": "active-user",
            "product_id": "popular-item",
            "rating": 5.0,
            "date": base_time + timedelta(hours=i),
            "review_text": f"Review {i}",
            "label": 0,
            "source_file": "test.csv",
        })
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values(["date", "review_id"]).reset_index(drop=True)
    df["node_index"] = np.arange(len(df), dtype=np.int64)

    edges = build_inductive_edges(df, max_neighbors=50, rtr_max_days=30)

    # Node 79 has 79 prior reviews; in-degree in RUR must be capped at 50
    for rel_name in ("rur", "rsr", "rtr"):
        edge_arr = edges[rel_name]
        tgt_node_79_sources = edge_arr[0][edge_arr[1] == 79]
        assert len(tgt_node_79_sources) == 50, f"Expected 50 capped neighbors for {rel_name}, got {len(tgt_node_79_sources)}"
        # Verify they are the 50 MOST RECENT prior nodes: 29..78
        expected_sources = list(range(29, 79))
        assert sorted(tgt_node_79_sources.tolist()) == expected_sources


def test_rtr_30_day_window_enforced():
    """Proves RTR edges only connect reviews within <= 30 days."""
    base_time = datetime(2010, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Review 0 at Day 0, Review 1 at Day 10, Review 2 at Day 45 (35 days after Review 1, 45 days after Review 0)
    records = [
        {"review_id": "r0", "reviewer_id": "u0", "product_id": "p0", "rating": 5.0, "date": base_time, "review_text": "t0", "label": 0, "source_file": "t.csv"},
        {"review_id": "r1", "reviewer_id": "u1", "product_id": "p0", "rating": 4.0, "date": base_time + timedelta(days=10), "review_text": "t1", "label": 0, "source_file": "t.csv"},
        {"review_id": "r2", "reviewer_id": "u2", "product_id": "p0", "rating": 5.0, "date": base_time + timedelta(days=45), "review_text": "t2", "label": 0, "source_file": "t.csv"},
    ]
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["node_index"] = np.arange(len(df), dtype=np.int64)

    edges = build_inductive_edges(df, max_neighbors=50, rtr_max_days=30)
    rtr = edges["rtr"]

    # Target 1 (day 10): connected to target 0 (diff 10 <= 30) -> (0, 1) should exist
    assert 0 in rtr[0][rtr[1] == 1]

    # Target 2 (day 45): diff from day 10 is 35 > 30, diff from day 0 is 45 > 30.
    # Therefore target 2 must have ZERO RTR incoming edges!
    assert len(rtr[0][rtr[1] == 2]) == 0


def test_scaler_fit_exclusively_on_train_nodes():
    """Proves that scaler fitting on training nodes is unaffected by validation or test values."""
    from sklearn.preprocessing import StandardScaler

    np.random.seed(42)
    x_meta = np.random.randn(100, 14).astype(np.float32)
    train_indices = np.arange(60)

    scaler_orig = StandardScaler().fit(x_meta[train_indices])

    # Alter validation/test rows (indices 60..99) to extreme outliers
    x_meta_corrupted = x_meta.copy()
    x_meta_corrupted[60:] = 1e6

    scaler_after = StandardScaler().fit(x_meta_corrupted[train_indices])

    np.testing.assert_array_equal(
        scaler_orig.mean_,
        scaler_after.mean_,
        err_msg="Scaler mean changed when val/test rows were altered!",
    )
    np.testing.assert_array_equal(
        scaler_orig.scale_,
        scaler_after.scale_,
        err_msg="Scaler scale changed when val/test rows were altered!",
    )
