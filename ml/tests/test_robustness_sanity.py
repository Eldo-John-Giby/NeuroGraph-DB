"""
Sanity test verifying that progressive attacks degrade text-only model performance monotonically.
"""

import pytest
from ml.train import train_single_run
from ml.data import get_artifacts_dir
from ml.mock_data import generate_all_mock_artifacts
import os


@pytest.fixture(scope="module")
def ensure_mock_data():
    artifacts_dir = get_artifacts_dir()
    clean_path = os.path.join(artifacts_dir, "graph", "yelpchi_graph.pt")
    if not os.path.exists(clean_path):
        generate_all_mock_artifacts(artifacts_dir)
    return artifacts_dir


def test_text_only_attack_monotonic_degradation(ensure_mock_data):
    """
    Sanity test: Stronger semantic attacks (L1 -> L2 -> L3) should strictly decrease
    or not increase text_only baseline AUC.
    """
    variants = ["clean", "sem_L1", "sem_L2", "sem_L3"]
    aucs = []

    for var in variants:
        res = train_single_run(
            model_name="text_only",
            train_variant="clean",
            eval_variant=var,
            seed=42,
            config={"epochs": 20, "loss_type": "focal"},
            artifacts_dir=ensure_mock_data,
            save_artifacts=False
        )
        aucs.append(res["metrics"]["auc"])

    # Verify that clean >= sem_L1 >= sem_L2 >= sem_L3 (allowing small numerical tolerance)
    for i in range(len(aucs) - 1):
        assert aucs[i] >= aucs[i + 1] - 0.05, f"Expected {variants[i]} ({aucs[i]}) >= {variants[i+1]} ({aucs[i+1]})"
    # End-to-end check: Clean should definitely be higher than sem_L3
    assert aucs[0] > aucs[-1], f"Clean AUC ({aucs[0]}) must be strictly greater than sem_L3 AUC ({aucs[-1]})"
