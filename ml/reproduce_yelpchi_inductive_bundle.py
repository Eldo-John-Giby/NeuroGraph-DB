#!/usr/bin/env python3
"""Verify an honest inductive YelpChi bundle and reproduce one fixed known-node score."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.models.roberta_relation_gnn import RobertaRelationGNN


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True, help="Path to inductive bundle directory")
    parser.add_argument("--manifest-sha256", required=True, help="Trusted hash from run record")
    args = parser.parse_args()

    bundle = Path(args.bundle_dir).resolve()
    manifest_path = bundle / "run_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing bundle manifest at {manifest_path}")

    if sha256(manifest_path) != args.manifest_sha256:
        raise ValueError("Manifest SHA256 does not match trusted run record")

    manifest = json.loads(manifest_path.read_text())
    if manifest.get("bundle_type") != "raw_yelpchi_inductive_roberta_gnn_v1":
        raise ValueError(f"Unexpected bundle type: {manifest.get('bundle_type')}")

    for name, expected in manifest["files"].items():
        file_path = bundle / name
        if not file_path.is_file():
            raise FileNotFoundError(f"Missing bundle file: {name}")
        observed_sha = sha256(file_path)
        if observed_sha != expected:
            raise ValueError(f"Checksum mismatch for {name}: expected {expected}, got {observed_sha}")

    config = json.loads((bundle / "model_config.json").read_text())
    graph = torch.load(bundle / "serving_graph.pt", map_location="cpu", weights_only=False)

    # Label-free audit: assert absolutely no labels or masks inside serving graph
    forbidden = {"y", "labels", "train_mask", "validation_mask", "test_mask"}.intersection(graph)
    if forbidden:
        raise ValueError(f"Label leakage: serving graph contains forbidden fields {forbidden}")

    checkpoint = torch.load(bundle / "model_state.pt", map_location="cpu", weights_only=False)
    model = RobertaRelationGNN(
        text_dim=int(config["text_dim"]),
        meta_dim=int(config["meta_dim"]),
        hidden_dim=int(config["hidden_dim"]),
        dropout=float(config["dropout"]),
    )
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()

    edges = {
        name: graph[f"edge_index_{name}"]
        for name in config["relations"]
    }

    with torch.inference_mode():
        scores = torch.softmax(model(graph["x_text"], graph["x_meta"], edges), dim=1)[:, 1].cpu().numpy()

    fixed = manifest["fixed_review"]
    node_index = int(fixed["node_index"])
    if graph["review_ids"][node_index] != fixed["review_id"]:
        raise ValueError(f"Fixed review ID mismatch: expected {fixed['review_id']}, got {graph['review_ids'][node_index]}")

    observed = float(scores[node_index])
    expected = float(fixed["expected_fraud_score"])
    tolerance = float(fixed["tolerance"])
    if abs(observed - expected) > tolerance:
        raise ValueError(
            f"Fixed review score reproduction failed: observed {observed}, expected {expected}, tolerance {tolerance}"
        )

    print(
        json.dumps(
            {
                "status": "passed",
                "model_family": manifest.get("model_family"),
                "relation_policy": manifest.get("relation_policy"),
                "review_id": fixed["review_id"],
                "node_index": node_index,
                "fraud_score": observed,
                "threshold": manifest["threshold"],
                "labels_accessed": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
