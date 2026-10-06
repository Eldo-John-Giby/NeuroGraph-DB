"""
Unit tests for evaluation metrics sanity.
"""

import numpy as np
from ml.evaluate import compute_metrics_at_threshold


def test_perfect_predictor():
    y_true = np.array([0, 0, 0, 1, 1, 1])
    y_prob = np.array([0.01, 0.05, 0.10, 0.90, 0.95, 0.99])
    res = compute_metrics_at_threshold(y_true, y_prob, threshold=0.5)

    assert res["auc"] == 1.0
    assert res["pr_auc"] == 1.0
    assert res["f1_macro"] == 1.0


def test_random_predictor():
    rng = np.random.default_rng(42)
    y_true = rng.choice([0, 1], size=1000, p=[0.85, 0.15])
    y_prob = rng.uniform(0, 1, size=1000)
    res = compute_metrics_at_threshold(y_true, y_prob, threshold=0.5)

    # Random guessing should have ROC-AUC around 0.5 (+- 0.05)
    assert 0.45 <= res["auc"] <= 0.55
