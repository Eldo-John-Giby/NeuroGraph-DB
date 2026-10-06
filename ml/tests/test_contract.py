"""
Unit tests for data artifact contract validation.
"""

import os
import pytest
import torch
from ml.data import load_clean_graph, load_variant, get_artifacts_dir, validate_graph_dict
from ml.mock_data import generate_all_mock_artifacts


@pytest.fixture(scope="module")
def ensure_mock_data():
    artifacts_dir = get_artifacts_dir()
    clean_path = os.path.join(artifacts_dir, "graph", "yelpchi_graph.pt")
    if not os.path.exists(clean_path):
        generate_all_mock_artifacts(artifacts_dir)
    return artifacts_dir


def test_clean_graph_contract(ensure_mock_data):
    clean_dict = load_clean_graph(ensure_mock_data)
    validate_graph_dict(clean_dict, is_variant=False)

    n = len(clean_dict["review_ids"])
    assert clean_dict["x_sem"].shape == (n, 768)
    assert clean_dict["x_meta"].shape[0] == n
    assert clean_dict["y"].shape == (n,)
    assert clean_dict["train_mask"].shape == (n,)
    assert clean_dict["val_mask"].shape == (n,)
    assert clean_dict["test_mask"].shape == (n,)

    # Splits must form a valid partition
    total = clean_dict["train_mask"].sum() + clean_dict["val_mask"].sum() + clean_dict["test_mask"].sum()
    assert total.item() == n


def test_variants_contract(ensure_mock_data):
    variants = [
        "sem_L1", "sem_L2", "sem_L3",
        "topo_p10", "topo_p30", "topo_p50", "topo_hub_p30",
        "both_L3_p30"
    ]
    clean_dict = load_clean_graph(ensure_mock_data)

    for var in variants:
        var_dict = load_variant(var, ensure_mock_data)
        validate_graph_dict(var_dict, is_variant=True)

        assert var_dict["variant"] == var
        assert var_dict["attacked_mask"].shape == clean_dict["y"].shape
        assert torch.equal(var_dict["train_mask"], clean_dict["train_mask"])
        assert torch.equal(var_dict["val_mask"], clean_dict["val_mask"])
        assert torch.equal(var_dict["test_mask"], clean_dict["test_mask"])
        assert torch.equal(var_dict["y"], clean_dict["y"])
        assert var_dict["review_ids"] == clean_dict["review_ids"]
