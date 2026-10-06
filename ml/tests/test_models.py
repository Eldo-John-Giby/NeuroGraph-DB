"""
Unit tests for model architectures and attention weight properties.
"""

import pytest
import torch
from ml.models import build_model, TextOnlyMLP, GNNOnly, ConcatFusion, NeuroGraph


@pytest.fixture
def mock_batch_tensors():
    n_nodes = 50
    x_sem = torch.randn(n_nodes, 768)
    x_meta = torch.randn(n_nodes, 32)
    # Generate random edges for rur, rsr, rtr
    src = torch.randint(0, n_nodes, (100,))
    dst = torch.randint(0, n_nodes, (100,))
    edge_index = torch.stack([src, dst], dim=0)
    edge_index_dict = {
        "rur": edge_index,
        "rsr": edge_index,
        "rtr": edge_index,
    }
    return x_sem, x_meta, edge_index_dict, n_nodes


def test_text_only_forward(mock_batch_tensors):
    x_sem, _, _, n_nodes = mock_batch_tensors
    model = build_model("text_only", sem_dim=768, d_model=64)
    out = model(x_sem)
    assert out.shape == (n_nodes, 2)


def test_gnn_only_forward(mock_batch_tensors):
    _, x_meta, edge_index_dict, n_nodes = mock_batch_tensors
    model = build_model("gnn_only", meta_dim=32, d_model=64)
    out = model(x_meta=x_meta, edge_index_dict=edge_index_dict)
    assert out.shape == (n_nodes, 2)


def test_concat_forward(mock_batch_tensors):
    x_sem, x_meta, edge_index_dict, n_nodes = mock_batch_tensors
    model = build_model("concat", sem_dim=768, meta_dim=32, d_model=64)
    out = model(x_sem=x_sem, x_meta=x_meta, edge_index_dict=edge_index_dict)
    assert out.shape == (n_nodes, 2)


def test_neurograph_forward_and_attention(mock_batch_tensors):
    x_sem, x_meta, edge_index_dict, n_nodes = mock_batch_tensors
    model = build_model("neurograph", sem_dim=768, meta_dim=32, d_model=64, num_heads=4)

    # 1. Forward logits shape
    logits = model(x_sem=x_sem, x_meta=x_meta, edge_index_dict=edge_index_dict, return_attention=False)
    assert logits.shape == (n_nodes, 2)

    # 2. Forward with attention weights (in eval mode to test deterministic softmax sum = 1)
    model.eval()
    with torch.no_grad():
        logits, attn_weights = model(x_sem=x_sem, x_meta=x_meta, edge_index_dict=edge_index_dict, return_attention=True)
    assert logits.shape == (n_nodes, 2)
    # Shape must be [N, 4] for 3 relations + 1 fused token
    assert attn_weights.shape == (n_nodes, 4)

    # 3. Attention weights must strictly sum to 1 across rows
    row_sums = attn_weights.sum(dim=-1)
    assert torch.allclose(row_sums, torch.ones(n_nodes), atol=1e-5), f"Attention weights must sum to 1 per node, got sums {row_sums}"
    assert (attn_weights >= 0.0).all(), "Attention weights must be non-negative"

