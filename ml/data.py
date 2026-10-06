"""
Data loading and validation module for NeuroGraph-DB.
Handles YelpChi graph contract validation, clean & variant graph loading,
and neighbor/full-batch data loading utilities for PyTorch / PyG.
"""

import os
import torch
from torch_geometric.data import Data
from typing import Dict, Any, Optional, Tuple, List


def get_artifacts_dir() -> str:
    default_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts"))
    return os.environ.get("ARTIFACTS_DIR", default_dir)


REQUIRED_CLEAN_KEYS = {
    "x_sem", "x_meta", "y",
    "edge_index_rur", "edge_index_rsr", "edge_index_rtr",
    "train_mask", "val_mask", "test_mask", "review_ids"
}

REQUIRED_VARIANT_KEYS = REQUIRED_CLEAN_KEYS.union({"attacked_mask", "variant"})


def validate_graph_dict(data_dict: Dict[str, Any], is_variant: bool = False) -> None:
    """Validates that a graph dictionary strictly satisfies the NeuroGraph-DB contract."""
    req_keys = REQUIRED_VARIANT_KEYS if is_variant else REQUIRED_CLEAN_KEYS
    missing = req_keys - set(data_dict.keys())
    if missing:
        raise ValueError(f"Graph dictionary is missing required contract keys: {missing}")

    x_sem = data_dict["x_sem"]
    x_meta = data_dict["x_meta"]
    y = data_dict["y"]
    rur = data_dict["edge_index_rur"]
    rsr = data_dict["edge_index_rsr"]
    rtr = data_dict["edge_index_rtr"]
    tr_mask = data_dict["train_mask"]
    va_mask = data_dict["val_mask"]
    te_mask = data_dict["test_mask"]
    review_ids = data_dict["review_ids"]

    # Check types
    if not isinstance(x_sem, torch.Tensor) or x_sem.dtype != torch.float32:
        raise TypeError("x_sem must be a float32 torch.Tensor")
    if not isinstance(x_meta, torch.Tensor) or x_meta.dtype != torch.float32:
        raise TypeError("x_meta must be a float32 torch.Tensor")
    if not isinstance(y, torch.Tensor) or y.dtype != torch.int64:
        raise TypeError("y must be an int64 torch.Tensor")
    if not isinstance(tr_mask, torch.Tensor) or tr_mask.dtype != torch.bool:
        raise TypeError("train_mask must be a bool torch.Tensor")
    if not isinstance(va_mask, torch.Tensor) or va_mask.dtype != torch.bool:
        raise TypeError("val_mask must be a bool torch.Tensor")
    if not isinstance(te_mask, torch.Tensor) or te_mask.dtype != torch.bool:
        raise TypeError("test_mask must be a bool torch.Tensor")
    if not isinstance(review_ids, list) or len(review_ids) == 0 or not isinstance(review_ids[0], str):
        raise TypeError("review_ids must be a non-empty list of str")

    # Dimensions
    n_nodes = len(review_ids)
    if x_sem.ndim != 2 or x_sem.shape[0] != n_nodes or x_sem.shape[1] != 768:
        raise ValueError(f"x_sem must have shape [{n_nodes}, 768], got {list(x_sem.shape)}")
    if x_meta.ndim != 2 or x_meta.shape[0] != n_nodes:
        raise ValueError(f"x_meta must have shape [{n_nodes}, F], got {list(x_meta.shape)}")
    if y.ndim != 1 or y.shape[0] != n_nodes:
        raise ValueError(f"y must have shape [{n_nodes}], got {list(y.shape)}")
    if tr_mask.shape[0] != n_nodes or va_mask.shape[0] != n_nodes or te_mask.shape[0] != n_nodes:
        raise ValueError("Masks must have shape [N]")

    # Check split disjointness and completeness
    total_split_nodes = tr_mask.sum().item() + va_mask.sum().item() + te_mask.sum().item()
    if (tr_mask & va_mask).any() or (tr_mask & te_mask).any() or (va_mask & te_mask).any():
        raise ValueError("train_mask, val_mask, and test_mask must be disjoint")
    if total_split_nodes != n_nodes:
        raise ValueError(f"Split masks sum to {total_split_nodes}, expected {n_nodes}")

    # Edge indices
    for name, ei in [("rur", rur), ("rsr", rsr), ("rtr", rtr)]:
        if not isinstance(ei, torch.Tensor) or ei.dtype != torch.int64:
            raise TypeError(f"edge_index_{name} must be an int64 torch.Tensor")
        if ei.ndim != 2 or ei.shape[0] != 2:
            raise ValueError(f"edge_index_{name} must have shape [2, E], got {list(ei.shape)}")
        if ei.numel() > 0:
            if ei.min() < 0 or ei.max() >= n_nodes:
                raise ValueError(f"edge_index_{name} node indices out of range [0, {n_nodes-1}]")

    if is_variant:
        att_mask = data_dict["attacked_mask"]
        if not isinstance(att_mask, torch.Tensor) or att_mask.dtype != torch.bool or att_mask.shape[0] != n_nodes:
            raise ValueError("attacked_mask must be a bool torch.Tensor of shape [N]")
        if not isinstance(data_dict["variant"], str):
            raise TypeError("variant must be a str")


def load_clean_graph(artifacts_dir: Optional[str] = None) -> Dict[str, Any]:
    """Loads and validates the clean YelpChi graph."""
    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()
    path = os.path.join(artifacts_dir, "graph", "yelpchi_graph.pt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Clean graph not found at {path}. Run ml/mock_data.py or ingest pipeline.")
    data_dict = torch.load(path, weights_only=False)
    validate_graph_dict(data_dict, is_variant=False)
    return data_dict


def load_variant(name: str, artifacts_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads and validates a graph variant (or 'clean').
    Asserts that splits and review_ids are identical to the clean graph.
    """
    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()

    clean_dict = load_clean_graph(artifacts_dir)
    if name == "clean":
        clean_dict_copy = dict(clean_dict)
        clean_dict_copy["variant"] = "clean"
        clean_dict_copy["attacked_mask"] = torch.zeros_like(clean_dict["y"], dtype=torch.bool)
        return clean_dict_copy

    var_path = os.path.join(artifacts_dir, "graph", "variants", f"{name}.pt")
    if not os.path.exists(var_path):
        raise FileNotFoundError(f"Variant graph '{name}' not found at {var_path}")

    var_dict = torch.load(var_path, weights_only=False)
    validate_graph_dict(var_dict, is_variant=True)

    # Assert splits are strictly identical
    assert torch.equal(clean_dict["train_mask"], var_dict["train_mask"]), "Variant train_mask must equal clean"
    assert torch.equal(clean_dict["val_mask"], var_dict["val_mask"]), "Variant val_mask must equal clean"
    assert torch.equal(clean_dict["test_mask"], var_dict["test_mask"]), "Variant test_mask must equal clean"
    assert torch.equal(clean_dict["y"], var_dict["y"]), "Variant labels y must equal clean"
    assert clean_dict["review_ids"] == var_dict["review_ids"], "Variant review_ids must equal clean"

    return var_dict


class RelationGraphBatch:
    """Container holding multi-relation graph tensors."""
    def __init__(
        self,
        x_sem: torch.Tensor,
        x_meta: torch.Tensor,
        edge_index_dict: Dict[str, torch.Tensor],
        y: Optional[torch.Tensor] = None,
        train_mask: Optional[torch.Tensor] = None,
        val_mask: Optional[torch.Tensor] = None,
        test_mask: Optional[torch.Tensor] = None,
        attacked_mask: Optional[torch.Tensor] = None,
        review_ids: Optional[List[str]] = None,
        node_idx: Optional[torch.Tensor] = None,
    ):
        self.x_sem = x_sem
        self.x_meta = x_meta
        self.edge_index_dict = edge_index_dict
        self.y = y
        self.train_mask = train_mask
        self.val_mask = val_mask
        self.test_mask = test_mask
        self.attacked_mask = attacked_mask
        self.review_ids = review_ids
        self.node_idx = node_idx if node_idx is not None else torch.arange(x_sem.shape[0])

    def to(self, device: torch.device) -> "RelationGraphBatch":
        return RelationGraphBatch(
            x_sem=self.x_sem.to(device),
            x_meta=self.x_meta.to(device),
            edge_index_dict={k: v.to(device) for k, v in self.edge_index_dict.items()},
            y=self.y.to(device) if self.y is not None else None,
            train_mask=self.train_mask.to(device) if self.train_mask is not None else None,
            val_mask=self.val_mask.to(device) if self.val_mask is not None else None,
            test_mask=self.test_mask.to(device) if self.test_mask is not None else None,
            attacked_mask=self.attacked_mask.to(device) if self.attacked_mask is not None else None,
            review_ids=self.review_ids,
            node_idx=self.node_idx.to(device) if self.node_idx is not None else None,
        )


def graph_dict_to_batch(data_dict: Dict[str, Any]) -> RelationGraphBatch:
    """Converts a loaded dictionary to RelationGraphBatch."""
    return RelationGraphBatch(
        x_sem=data_dict["x_sem"],
        x_meta=data_dict["x_meta"],
        edge_index_dict={
            "rur": data_dict["edge_index_rur"],
            "rsr": data_dict["edge_index_rsr"],
            "rtr": data_dict["edge_index_rtr"],
        },
        y=data_dict.get("y"),
        train_mask=data_dict.get("train_mask"),
        val_mask=data_dict.get("val_mask"),
        test_mask=data_dict.get("test_mask"),
        attacked_mask=data_dict.get("attacked_mask"),
        review_ids=data_dict.get("review_ids"),
    )
