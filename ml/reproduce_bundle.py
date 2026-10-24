"""Reproduce a fixed known-node score from a self-contained NeuroGraph bundle.

This command refuses incomplete or checksum-mismatched bundles. A successful
run proves numerical reproduction for the bundled known node only; it does not
independently authenticate dataset licensing or validate model performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.data import validate_graph_dict
from ml.models import build_model


REQUIRED = {
    "dataset": ("name", "source_file", "source_sha256", "synthetic", "license_evidence_file", "license_evidence_sha256"),
    "model": ("architecture", "config_file", "config_sha256", "checkpoint_file", "checkpoint_sha256"),
    "tokenizer": ("model_id", "revision"),
    "preprocessing": ("version", "manifest_file", "manifest_sha256", "scaler_file", "scaler_sha256"),
    "graph": ("file", "sha256", "split_identity"),
    "run": ("run_id", "seed", "threshold", "threshold_source", "test_predictions_file", "test_predictions_sha256"),
    "fixed_review": ("review_id", "expected_fraud_score", "absolute_tolerance"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bundle_file(bundle_dir: Path, relative: str, expected_hash: str) -> Path:
    candidate = (bundle_dir / relative).resolve()
    if bundle_dir.resolve() not in candidate.parents:
        raise ValueError(f"bundle path escapes bundle directory: {relative}")
    if not candidate.is_file():
        raise ValueError(f"required bundle file is missing: {relative}")
    actual = sha256(candidate)
    if actual != expected_hash:
        raise ValueError(f"SHA-256 mismatch for {relative}: expected {expected_hash}, got {actual}")
    return candidate


def load_manifest(path: Path) -> tuple[dict, Path]:
    bundle_dir = path.resolve().parent
    manifest = json.loads(path.read_text(encoding="utf-8"))
    missing = [f"{section}.{key}" for section, keys in REQUIRED.items()
               for key in keys if key not in manifest.get(section, {})]
    if missing:
        raise ValueError("manifest is incomplete: " + ", ".join(missing))
    if manifest["dataset"]["synthetic"] is not False:
        raise ValueError("synthetic datasets cannot be used as real-model evidence")
    if manifest["run"]["threshold_source"] != "validation":
        raise ValueError("threshold must be selected from validation data")
    if not 0 <= float(manifest["run"]["threshold"]) <= 1:
        raise ValueError("run threshold must be in [0, 1]")
    if not 0 <= float(manifest["fixed_review"]["expected_fraud_score"]) <= 1:
        raise ValueError("fixed expected score must be in [0, 1]")
    if float(manifest["fixed_review"]["absolute_tolerance"]) < 0:
        raise ValueError("absolute tolerance must be nonnegative")
    return manifest, bundle_dir


def reproduce(manifest_path: Path, expected_manifest_sha256: str) -> dict:
    if not manifest_path.is_file():
        raise ValueError(f"run manifest is missing: {manifest_path}")
    actual_manifest_sha256 = sha256(manifest_path)
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise ValueError(f"run manifest SHA-256 mismatch: expected {expected_manifest_sha256}, got {actual_manifest_sha256}")
    manifest, directory = load_manifest(manifest_path)
    dataset = manifest["dataset"]
    bundle_file(directory, dataset["source_file"], dataset["source_sha256"])
    bundle_file(directory, dataset["license_evidence_file"], dataset["license_evidence_sha256"])
    model_info = manifest["model"]
    config_path = bundle_file(directory, model_info["config_file"], model_info["config_sha256"])
    checkpoint_path = bundle_file(directory, model_info["checkpoint_file"], model_info["checkpoint_sha256"])
    prep = manifest["preprocessing"]
    bundle_file(directory, prep["manifest_file"], prep["manifest_sha256"])
    bundle_file(directory, prep["scaler_file"], prep["scaler_sha256"])
    graph_info = manifest["graph"]
    graph_path = bundle_file(directory, graph_info["file"], graph_info["sha256"])
    run = manifest["run"]
    bundle_file(directory, run["test_predictions_file"], run["test_predictions_sha256"])

    tokenizer_revision = str(manifest["tokenizer"]["revision"])
    if len(tokenizer_revision) < 20 or tokenizer_revision.lower() in {"main", "latest"}:
        raise ValueError("tokenizer revision must be pinned to an immutable revision identifier")
    if model_info["architecture"] != "neurograph":
        raise ValueError("unsupported architecture in bundle")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if config.get("model") != "neurograph":
        raise ValueError("model config architecture does not match manifest")
    graph = torch.load(graph_path, map_location="cpu", weights_only=False)
    validate_graph_dict(graph)
    split_payload = {
        "review_ids": graph["review_ids"],
        "train": graph["train_mask"].tolist(),
        "validation": graph["val_mask"].tolist(),
        "test": graph["test_mask"].tolist(),
    }
    split_sha = hashlib.sha256(json.dumps(split_payload, separators=(",", ":")).encode()).hexdigest()
    if graph_info["split_identity"] != split_sha:
        raise ValueError("graph review/split identity does not match manifest")

    model = build_model(
        "neurograph", sem_dim=config["sem_dim"], meta_dim=config["meta_dim"],
        d_model=config["d_model"], num_heads=config["num_heads"],
        dropout=config["dropout"], use_sem_in_gnn=config["use_sem_in_gnn"],
        relations=tuple(config["relations"]),
    )
    state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval()
    review_id = str(manifest["fixed_review"]["review_id"])
    if review_id not in graph["review_ids"]:
        raise ValueError(f"fixed review id is absent from graph: {review_id}")
    node = graph["review_ids"].index(review_id)
    with torch.inference_mode():
        logits = model(graph["x_sem"], graph["x_meta"], {
            "rur": graph["edge_index_rur"], "rsr": graph["edge_index_rsr"], "rtr": graph["edge_index_rtr"]
        })
        score = float(torch.softmax(logits, dim=1)[node, 1].item())
        all_probs = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
    # Re-run the repository's declared validation-only threshold selection.
    from ml.evaluate import find_best_threshold_on_val
    val_mask = graph["val_mask"].cpu().numpy()
    selected_threshold = find_best_threshold_on_val(
        graph["y"].cpu().numpy()[val_mask], all_probs[val_mask]
    )
    if abs(selected_threshold - float(run["threshold"])) > 1e-8:
        raise ValueError(f"validation-selected threshold mismatch: bundle={run['threshold']} recomputed={selected_threshold}")
    expected = float(manifest["fixed_review"]["expected_fraud_score"])
    tolerance = float(manifest["fixed_review"]["absolute_tolerance"])
    result = {"run_id": run["run_id"], "review_id": review_id,
              "fraud_score": score, "expected_fraud_score": expected,
              "absolute_error": abs(score - expected), "tolerance": tolerance,
              "validation_threshold": selected_threshold,
              "reproduced": abs(score - expected) <= tolerance}
    if not result["reproduced"]:
        raise ValueError("score did not reproduce: " + json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="path to bundle run_manifest.json")
    parser.add_argument("--manifest-sha256", required=True,
                        help="trusted SHA-256 of the run manifest (pin this outside the bundle)")
    args = parser.parse_args()
    try:
        result = reproduce(args.manifest, args.manifest_sha256)
    except Exception as exc:
        print(f"BUNDLE_REPRODUCTION_FAILED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
