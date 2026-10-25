#!/usr/bin/env python3
"""Verify a multimodal YelpChi bundle and reproduce one fixed known-node score."""

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
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--manifest-sha256", required=True, help="Trusted hash from a run record outside this bundle")
    args = parser.parse_args()
    bundle = Path(args.bundle_dir).resolve()
    manifest_path = bundle / "run_manifest.json"
    if sha256(manifest_path) != args.manifest_sha256:
        raise ValueError("manifest SHA256 does not match trusted run record")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("bundle_type") not in {"yelpchi_multimodal_roberta_pyg_gnn", "raw_yelpchi_multimodal_roberta_pyg_gnn"}:
        raise ValueError("unexpected bundle type")
    for name, expected in manifest["files"].items():
        if sha256(bundle / name) != expected:
            raise ValueError(f"checksum mismatch: {name}")
    config = json.loads((bundle / "model_config.json").read_text())
    graph = torch.load(bundle / "serving_graph.pt", map_location="cpu", weights_only=False)
    checkpoint = torch.load(bundle / "model_state.pt", map_location="cpu", weights_only=False)
    model = RobertaRelationGNN(
        text_dim=int(config["text_dim"]), meta_dim=int(config["meta_dim"]),
        hidden_dim=int(config["hidden_dim"]), dropout=float(config["dropout"]),
    )
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    edges = {name: graph[f"edge_index_{name}"] for name in ("rur", "rsr", "rtr")}
    with torch.inference_mode():
        scores = torch.softmax(model(graph["x_text"], graph["x_meta"], edges), dim=1)[:, 1]
    fixed = manifest["fixed_review"]
    node_index = int(fixed["node_index"])
    if graph["review_ids"][node_index] != fixed["review_id"]:
        raise ValueError("fixed review ID is not bound to its recorded node index")
    observed = float(scores[node_index])
    if abs(observed - float(fixed["expected_fraud_score"])) > float(fixed["tolerance"]):
        raise ValueError("fixed review score is not reproducible within tolerance")
    print(json.dumps({"status": "passed", "review_id": fixed["review_id"], "node_index": node_index, "fraud_score": observed, "threshold": manifest["threshold"], "labels_accessed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
