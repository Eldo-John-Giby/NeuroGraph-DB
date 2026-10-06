"""
Unit tests to verify no data leakage in threshold selection.
"""

import numpy as np
from ml.evaluate import find_best_threshold_on_val, evaluate_predictions


def test_threshold_computation_isolated():
    # Validation split predictions
    y_val = np.array([0, 0, 0, 0, 1, 1])
    val_probs = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.8])

    # Test split has an entirely different distribution/attack
    y_test = np.array([0, 0, 1, 1])
    test_probs = np.array([0.45, 0.48, 0.52, 0.55])

    # Threshold computed strictly on val
    thresh = find_best_threshold_on_val(y_val, val_probs)
    assert 0.4 <= thresh <= 0.6

    # Test metrics evaluated with unchanged val threshold
    test_metrics = evaluate_predictions(y_test, test_probs, threshold=thresh)
    assert "f1_macro" in test_metrics
    assert test_metrics["threshold"] == round(thresh, 4)
