"""
Evaluation and Metrics Module for NeuroGraph-DB.
Computes ROC-AUC, PR-AUC, and F1-Macro.
Determines optimal classification threshold from validation set and applies to test set.
"""

import os
import json
import numpy as np
import torch
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
from typing import Dict, Any, Tuple, Optional


def compute_metrics_at_threshold(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> Dict[str, float]:
    """Computes AUC, PR-AUC, and F1-Macro given probabilities and a threshold."""
    y_pred = (y_prob >= threshold).astype(int)

    # Safe AUC computation
    if len(np.unique(y_true)) > 1:
        auc = float(roc_auc_score(y_true, y_prob))
        pr_auc = float(average_precision_score(y_true, y_prob))
    else:
        auc = 0.5
        pr_auc = float(np.mean(y_true))

    f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))

    return {
        "auc": round(auc, 4),
        "pr_auc": round(pr_auc, 4),
        "f1_macro": round(f1, 4),
        "threshold": round(float(threshold), 4),
    }


def find_best_threshold_on_val(y_val_true: np.ndarray, y_val_prob: np.ndarray, num_thresholds: int = 200) -> float:
    """Scans candidate thresholds on validation split to maximize F1-Macro."""
    thresholds = np.linspace(0.01, 0.99, num_thresholds)
    best_thresh = 0.5
    best_f1 = -1.0

    for th in thresholds:
        y_pred = (y_val_prob >= th).astype(int)
        f1 = f1_score(y_val_true, y_pred, average="macro", zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = float(th)

    return best_thresh


def evaluate_predictions(
    y_test_true: np.ndarray,
    y_test_prob: np.ndarray,
    threshold: float,
) -> Dict[str, float]:
    """Evaluates test predictions using a pre-determined threshold."""
    return compute_metrics_at_threshold(y_test_true, y_test_prob, threshold)


def save_metrics_json(
    metrics: Dict[str, Any],
    run_id: str,
    artifacts_dir: Optional[str] = None
) -> str:
    """Saves metrics.json to artifacts/results/<run_id>/metrics.json."""
    if artifacts_dir is None:
        from ml.data import get_artifacts_dir
        artifacts_dir = get_artifacts_dir()

    run_dir = os.path.join(artifacts_dir, "results", run_id)
    os.makedirs(run_dir, exist_ok=True)
    metrics_path = os.path.join(run_dir, "metrics.json")

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics_path
