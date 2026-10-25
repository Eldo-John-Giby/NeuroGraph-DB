#!/usr/bin/env python3
"""Train a reproducible, structured-feature YelpChi GNN baseline.

This is a transductive known-node benchmark: every YelpChi node and its RUR,
RSR, and RTR edges are visible during message passing, while labels are used
only for the deterministic train/validation/test node split.  It does not
claim to score arbitrary uploaded CSV rows or use RoBERTa, because the normal
YelpChi MAT representation has no aligned raw review text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sklearn
import torch
from scipy import io, sparse
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.preprocessing import StandardScaler

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ml.models import build_model


RELATION_KEYS = {"rur": "net_rur", "rsr": "net_rsr", "rtr": "net_rtr"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def require_source_evidence(path: Path, dataset_hash: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Source evidence is required and missing: {path}")
    data = json.loads(path.read_text())
    if data.get("dataset_sha256") != dataset_hash:
        raise ValueError("source evidence dataset_sha256 does not match --mat-path")
    if not data.get("dataset_ref") or not data.get("source_url"):
        raise ValueError("source evidence must contain dataset_ref and source_url")
    return data


def dense_features(value: Any) -> np.ndarray:
    matrix = value.toarray() if sparse.issparse(value) else np.asarray(value)
    if matrix.ndim != 2 or matrix.shape[1] != 32:
        raise ValueError(f"Expected a [N, 32] feature matrix, got {matrix.shape}")
    if not np.isfinite(matrix).all():
        raise ValueError("Feature matrix has non-finite values")
    return np.asarray(matrix, dtype=np.float32)


def adjacency_to_edge_index(value: Any, node_count: int) -> torch.Tensor:
    matrix = value.tocoo() if sparse.issparse(value) else sparse.coo_matrix(value)
    if matrix.shape != (node_count, node_count):
        raise ValueError(f"Relation shape {matrix.shape} does not match node count {node_count}")
    rows = np.asarray(matrix.row, dtype=np.int64)
    cols = np.asarray(matrix.col, dtype=np.int64)
    return torch.from_numpy(np.vstack((rows, cols))).long().contiguous()


def deterministic_split(labels: np.ndarray, seed: int) -> dict[str, np.ndarray]:
    all_indices = np.arange(labels.shape[0])
    first = StratifiedShuffleSplit(n_splits=1, train_size=0.60, random_state=seed)
    train_idx, held_out_idx = next(first.split(all_indices, labels))
    second = StratifiedShuffleSplit(n_splits=1, train_size=0.50, random_state=seed + 1)
    val_relative, test_relative = next(second.split(held_out_idx, labels[held_out_idx]))
    return {
        "train": np.sort(train_idx),
        "validation": np.sort(held_out_idx[val_relative]),
        "test": np.sort(held_out_idx[test_relative]),
    }


def threshold_from_validation(labels: np.ndarray, probabilities: np.ndarray) -> tuple[float, float]:
    best_threshold, best_score = 0.5, -1.0
    for threshold in np.linspace(0.01, 0.99, 199):
        score = f1_score(labels, probabilities >= threshold, average="macro", zero_division=0)
        if score > best_score:
            best_threshold, best_score = float(threshold), float(score)
    return best_threshold, best_score


def metrics(labels: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, float]:
    return {
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "pr_auc": float(average_precision_score(labels, probabilities)),
        "f1_macro": float(f1_score(labels, probabilities >= threshold, average="macro", zero_division=0)),
        "threshold": float(threshold),
    }


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def probability(model: torch.nn.Module, features: torch.Tensor, edges: dict[str, torch.Tensor]) -> torch.Tensor:
    with torch.inference_mode():
        logits = model(features, edges)
        return torch.softmax(logits, dim=1)[:, 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mat-path", required=True)
    parser.add_argument("--source-evidence", required=True, help="acquisition.json created by kaggle_yelpchi_download.py")
    parser.add_argument("--output-root", default="artifacts/verified_baselines")
    parser.add_argument("--run-record-dir", default="docs/runs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--dropout", type=float, default=0.20)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.0001)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    args = parser.parse_args()

    mat_path = Path(args.mat_path).resolve()
    dataset_hash = sha256(mat_path)
    source_evidence_path = Path(args.source_evidence).resolve()
    source_evidence = require_source_evidence(source_evidence_path, dataset_hash)
    source_report_path = source_evidence_path.parent / "inspection.json"
    if not source_report_path.is_file():
        raise FileNotFoundError("Run inspect_yelpchi.py first; missing " + str(source_report_path))
    source_report = json.loads(source_report_path.read_text())
    if source_report.get("mat_sha256") != dataset_hash:
        raise ValueError("inspection report hash does not match --mat-path")
    if source_report.get("selected_pipeline") != "structured_32_feature_gnn":
        raise ValueError("This trainer accepts only the inspected structured_32_feature_gnn pipeline")

    set_seed(args.seed)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda requested but CUDA is not available")
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else args.device if args.device != "auto" else "cpu")

    run_id = "yelpchi_gnn_seed{}_{}".format(args.seed, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    run_dir = Path(args.output_root).resolve() / run_id
    if run_dir.exists():
        raise FileExistsError(run_dir)
    run_dir.mkdir(parents=True)

    raw = io.loadmat(mat_path)
    required = {"features", "label", *RELATION_KEYS.values()}
    missing = required.difference(raw)
    if missing:
        raise ValueError("Dataset misses required fields: " + ", ".join(sorted(missing)))
    features = dense_features(raw["features"])
    labels = np.asarray(raw["label"]).reshape(-1).astype(np.int64)
    if labels.shape[0] != features.shape[0] or set(np.unique(labels)) != {0, 1}:
        raise ValueError("Expected binary 0/1 labels aligned to every feature row")
    splits = deterministic_split(labels, args.seed)
    scaler = StandardScaler().fit(features[splits["train"]])
    scaled_features = scaler.transform(features).astype(np.float32)
    review_ids = [f"yelpchi-node-{index:05d}" for index in range(features.shape[0])]
    edges_cpu = {relation: adjacency_to_edge_index(raw[key], features.shape[0]) for relation, key in RELATION_KEYS.items()}
    x_cpu = torch.from_numpy(scaled_features)
    edges = {relation: edge.to(device) for relation, edge in edges_cpu.items()}
    x = x_cpu.to(device)
    labels_tensor = torch.from_numpy(labels).long().to(device)
    split_tensors = {name: torch.from_numpy(indices).long().to(device) for name, indices in splits.items()}

    config = {
        "schema_version": 1,
        "model_name": "gnn_only",
        "architecture": "RelationAwareGraphSAGE",
        "feature_mode": "structured_32_feature_only",
        "tokenizer": {"applicable": False, "revision": None, "reason": "YelpChi MAT has no aligned review text"},
        "meta_dim": 32,
        "hidden_dim": args.hidden_dim,
        "dropout": args.dropout,
        "relations": list(RELATION_KEYS),
        "use_sem_in_gnn": False,
        "optimizer": {"name": "AdamW", "learning_rate": args.learning_rate, "weight_decay": args.weight_decay},
        "loss": "cross_entropy_class_weighted",
        "seed": args.seed,
        "split": {"method": "StratifiedShuffleSplit", "train": 0.60, "validation": 0.20, "test": 0.20, "seed": args.seed},
        "evaluation_protocol": "transductive_known_node",
        "source_report_sha256": sha256(source_report_path),
        "source_evidence_sha256": sha256(source_evidence_path),
    }
    json_dump(run_dir / "model_config.json", config)
    scaler_payload = {
        "schema_version": 1,
        "fitted_on_split": "train",
        "feature_count": 32,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "zero_variance_features": np.flatnonzero(scaler.scale_ == 1.0).tolist(),
    }
    json_dump(run_dir / "preprocessing.json", scaler_payload)
    graph_contract = {
        "schema_version": 1,
        "graph_schema": "yelpchi-32-feature-rur-rsr-rtr-v1",
        "review_ids": review_ids,
        "x_meta": x_cpu,
        "edge_index_rur": edges_cpu["rur"],
        "edge_index_rsr": edges_cpu["rsr"],
        "edge_index_rtr": edges_cpu["rtr"],
    }
    graph_path = run_dir / "serving_graph.pt"
    torch.save(graph_contract, graph_path)
    np.savez_compressed(
        run_dir / "evaluation_targets.npz",
        labels=labels,
        train_indices=splits["train"],
        validation_indices=splits["validation"],
        test_indices=splits["test"],
    )

    class_counts = np.bincount(labels[splits["train"]], minlength=2)
    class_weights = class_counts.sum() / (2.0 * class_counts.astype(np.float64))
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32, device=device))
    model = build_model(
        "gnn_only",
        meta_dim=32,
        d_model=args.hidden_dim,
        dropout=args.dropout,
        relations=tuple(RELATION_KEYS),
        use_sem_in_gnn=False,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    best_state: dict[str, torch.Tensor] | None = None
    best_validation = -float("inf")
    best_epoch = -1
    stale_epochs = 0
    training_log: list[dict[str, float | int]] = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits = model(x, edges)
        loss = loss_fn(logits[split_tensors["train"]], labels_tensor[split_tensors["train"]])
        loss.backward()
        optimizer.step()
        model.eval()
        probabilities = probability(model, x, edges).detach().cpu().numpy()
        val_threshold, validation_f1 = threshold_from_validation(labels[splits["validation"]], probabilities[splits["validation"]])
        training_log.append({"epoch": epoch, "train_loss": float(loss.item()), "validation_f1_macro": validation_f1, "validation_threshold": val_threshold})
        if validation_f1 > best_validation + 1e-12:
            best_validation, best_epoch, stale_epochs = validation_f1, epoch, 0
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        else:
            stale_epochs += 1
            if stale_epochs >= args.patience:
                break
    if best_state is None:
        raise RuntimeError("Training did not produce a checkpoint")

    model.load_state_dict(best_state, strict=True)
    model.to(device).eval()
    probabilities = probability(model, x, edges).detach().cpu().numpy()
    threshold, validation_f1 = threshold_from_validation(labels[splits["validation"]], probabilities[splits["validation"]])
    test_metrics = metrics(labels[splits["test"]], probabilities[splits["test"]], threshold)
    checkpoint_path = run_dir / "model_state.pt"
    torch.save({"state_dict": best_state, "model_config": config}, checkpoint_path)
    predictions = [
        {"review_id": review_ids[index], "node_index": int(index), "split": split, "label": int(labels[index]), "fraud_score": float(probabilities[index])}
        for split, indices in splits.items()
        for index in indices
    ]
    json_dump(run_dir / "evaluation_predictions.json", {"rows": predictions})
    fixed_index = int(splits["test"][0])
    reproduction = {
        "schema_version": 1,
        "review_id": review_ids[fixed_index],
        "node_index": fixed_index,
        "expected_fraud_score": float(probabilities[fixed_index]),
        "tolerance": 0.000001,
        "labels_required_for_reproduction": False,
    }
    json_dump(run_dir / "fixed_review_reproduction.json", reproduction)
    json_dump(run_dir / "training_log.json", {"epochs": training_log})
    metrics_payload = {
        "best_epoch": best_epoch,
        "best_validation_f1_macro": best_validation,
        "selected_validation_threshold": threshold,
        "validation_f1_at_selected_threshold": validation_f1,
        "test": test_metrics,
        "class_counts_train": {"legitimate": int(class_counts[0]), "fraud": int(class_counts[1])},
    }
    json_dump(run_dir / "metrics.json", metrics_payload)

    tracked_files = [
        "model_state.pt", "model_config.json", "preprocessing.json", "serving_graph.pt",
        "evaluation_targets.npz", "evaluation_predictions.json", "fixed_review_reproduction.json",
        "training_log.json", "metrics.json",
    ]
    manifest = {
        "schema_version": 1,
        "bundle_type": "yelpchi_structured_feature_gnn_baseline",
        "provenance": "real_benchmark_data",
        "model_claim": "32-feature relation-aware GNN baseline; no raw-text or RoBERTa modality",
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {"path": str(mat_path), "sha256": dataset_hash, "source_evidence": source_evidence},
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "device": str(device),
            "scikit_learn": sklearn.__version__,
        },
        "config": config,
        "threshold": threshold,
        "metrics": metrics_payload,
        "fixed_review": reproduction,
        "files": {name: sha256(run_dir / name) for name in tracked_files},
    }
    manifest_path = run_dir / "run_manifest.json"
    json_dump(manifest_path, manifest)

    run_record_dir = Path(args.run_record_dir).resolve()
    run_record_dir.mkdir(parents=True, exist_ok=True)
    portable_record = {
        "run_id": run_id,
        "bundle_manifest_sha256": sha256(manifest_path),
        "dataset_sha256": dataset_hash,
        "model_claim": manifest["model_claim"],
        "evaluation_protocol": config["evaluation_protocol"],
        "selected_validation_threshold": threshold,
        "test_metrics": test_metrics,
        "bundle_location": str(run_dir),
        "reproduction_command": f"python ml/reproduce_yelpchi_gnn_bundle.py --bundle-dir {run_dir} --manifest-sha256 {sha256(manifest_path)}",
    }
    json_dump(run_record_dir / f"{run_id}.json", portable_record)
    print(json.dumps({"run_id": run_id, "bundle_dir": str(run_dir), "manifest_sha256": sha256(manifest_path), "run_record": str(run_record_dir / f'{run_id}.json')}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
