#!/usr/bin/env python3
"""Verify and reproduce a fixed known-node YelpChi GNN score without labels.

Only the serving graph (features, stable node IDs, and edges), model files, and
trusted manifest hash are loaded.  ``evaluation_targets.npz`` is forbidden in
this command so it cannot inspect ground-truth labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ml.models import build_model


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> int:
    print("BUNDLE_REPRODUCTION_FAILED: " + message, file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    bundle = Path(args.bundle_dir).resolve()
    manifest_path = bundle / "run_manifest.json"
    if not manifest_path.is_file():
        return fail("run_manifest.json is missing")
    actual_manifest_hash = sha256(manifest_path)
    if actual_manifest_hash != args.manifest_sha256.lower():
        return fail("trusted manifest SHA256 does not match")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("provenance") != "real_benchmark_data":
        return fail("bundle provenance is not real_benchmark_data")
    files = manifest.get("files", {})
    required = ("model_state.pt", "model_config.json", "preprocessing.json", "serving_graph.pt", "fixed_review_reproduction.json")
    for name in required:
        path = bundle / name
        if not path.is_file():
            return fail(name + " is missing")
        if files.get(name) != sha256(path):
            return fail(name + " SHA256 does not match the manifest")
    config = json.loads((bundle / "model_config.json").read_text())
    fixed = json.loads((bundle / "fixed_review_reproduction.json").read_text())
    graph = torch.load(bundle / "serving_graph.pt", map_location="cpu", weights_only=False)
    forbidden = {"y", "labels", "train_mask", "validation_mask", "test_mask"}.intersection(graph)
    if forbidden:
        return fail("serving graph contains forbidden label/split fields: " + ", ".join(sorted(forbidden)))
    review_ids = graph["review_ids"]
    index = int(fixed["node_index"])
    if not 0 <= index < len(review_ids) or review_ids[index] != fixed["review_id"]:
        return fail("fixed review identity does not match serving graph")
    model = build_model(
        "gnn_only",
        meta_dim=int(config["meta_dim"]),
        d_model=int(config["hidden_dim"]),
        dropout=float(config["dropout"]),
        relations=tuple(config["relations"]),
        use_sem_in_gnn=False,
    )
    checkpoint = torch.load(bundle / "model_state.pt", map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    edges = {relation: graph[f"edge_index_{relation}"] for relation in config["relations"]}
    with torch.inference_mode():
        scores = torch.softmax(model(graph["x_meta"], edges), dim=1)[:, 1]
    observed = float(scores[index])
    expected = float(fixed["expected_fraud_score"])
    tolerance = float(fixed["tolerance"])
    difference = abs(observed - expected)
    if difference > tolerance:
        return fail(f"score mismatch: observed={observed:.10f}, expected={expected:.10f}, tolerance={tolerance}")
    print(json.dumps({"status": "passed", "review_id": fixed["review_id"], "node_index": index, "fraud_score": observed, "threshold": manifest["threshold"], "difference": difference, "labels_accessed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
