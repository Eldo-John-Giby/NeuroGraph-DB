#!/usr/bin/env python3
"""Train an honest inductive RoBERTa + PyG GNN model on raw YelpChi review arrivals.

Evaluation protocol and model family: raw_yelpchi_inductive_roberta_gnn_v1
- Pinned to FacebookAI/roberta-base commit SHA.
- Timestamp-ordered arrival windows: 60% train, 20% validation, 20% test.
- Metadata scaler is fit exclusively on train nodes.
- Relations: inductive-rur-rsr-rtr-v1 (strictly historic to candidate, capped at 50 neighbors).
- Decision threshold selected exclusively on validation split.
- Test evaluated exactly once after threshold selection.
- All file checksums and reproduction proofs are sealed in a SHA256 run manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.models.roberta_relation_gnn import RobertaRelationGNN
from ml.train_yelpchi_multimodal import embed_text, evaluate, seed_everything, select_threshold, sha256


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inductive-graph-dir", required=True, help="Output directory from build_yelpchi_inductive_graph.py")
    parser.add_argument("--expected-node-count", type=int, default=47176)
    parser.add_argument("--output-root", required=True, help="Root directory for output bundle")
    parser.add_argument("--run-record-dir", required=True, help="Directory for small run record JSON")
    parser.add_argument("--roberta-model", default="FacebookAI/roberta-base")
    parser.add_argument("--roberta-revision", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--text-batch-size", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    graph_dir = Path(args.inductive_graph_dir).resolve()
    manifest_path, graph_path = graph_dir / "graph_manifest.json", graph_dir / "inductive_graph.pt"
    if not manifest_path.is_file() or not graph_path.is_file():
        raise FileNotFoundError(f"Missing inductive graph artifacts in {graph_dir}")

    graph_manifest = json.loads(manifest_path.read_text())
    if (
        graph_manifest.get("bundle_type") != "raw_yelpchi_inductive_graph"
        or graph_manifest["files"].get("inductive_graph_sha256") != sha256(graph_path)
    ):
        raise ValueError("Inductive graph manifest does not authenticate graph artifact")

    device = torch.device(args.device)
    seed_everything(args.seed)

    raw_graph = torch.load(graph_path, map_location="cpu", weights_only=False)
    review_ids = raw_graph["review_ids"]
    review_texts = raw_graph["review_text"]
    x_meta_original = raw_graph["x_meta"].numpy()
    labels = raw_graph["labels"].numpy().astype(np.int64)

    if len(review_ids) != args.expected_node_count:
        raise ValueError(f"Expected {args.expected_node_count} nodes, found {len(review_ids)}")
    if len(review_ids) != len(review_texts) or len(labels) != len(review_ids):
        raise ValueError("Inconsistent node identity, text, or label lengths in inductive graph")

    splits = {
        "train": np.array(raw_graph["splits"]["train"], dtype=np.int64),
        "validation": np.array(raw_graph["splits"]["validation"], dtype=np.int64),
        "test": np.array(raw_graph["splits"]["test"], dtype=np.int64),
    }

    # Strict causality constraint: fit scaler ONLY on train nodes
    scaler = StandardScaler().fit(x_meta_original[splits["train"]])
    x_meta_cpu = torch.from_numpy(scaler.transform(x_meta_original).astype(np.float32))

    # Frozen RoBERTa text embedding with masked-mean pooling
    x_text_cpu, tokenizer_info = embed_text(
        review_texts, args.roberta_model, args.roberta_revision, args.text_batch_size, args.max_length, device
    )

    edges_cpu = {
        "rur": raw_graph["edge_index_rur"].long().contiguous(),
        "rsr": raw_graph["edge_index_rsr"].long().contiguous(),
        "rtr": raw_graph["edge_index_rtr"].long().contiguous(),
    }

    run_id = f"raw_yelpchi_inductive_seed{args.seed}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = Path(args.output_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    config = {
        "schema_version": 1,
        "model_family": "raw_yelpchi_inductive_roberta_gnn_v1",
        "architecture": "inductive_roberta_relation_specific_pyg_graphsage_cross_attention",
        "relation_policy": "inductive-rur-rsr-rtr-v1",
        "evaluation_protocol": "inductive_temporal_replay",
        "max_neighbors_per_relation": int(graph_manifest.get("max_neighbors_per_relation", 50)),
        "text_dim": int(x_text_cpu.shape[1]),
        "meta_dim": int(x_meta_cpu.shape[1]),
        "hidden_dim": args.hidden_dim,
        "dropout": args.dropout,
        "relations": ["rur", "rsr", "rtr"],
        "tokenizer": tokenizer_info,
        "graph_manifest_sha256": sha256(manifest_path),
        "inductive_graph_sha256": sha256(graph_path),
        "seed": args.seed,
        "node_count": len(review_ids),
        "split": {
            "method": "chronological_arrival_windows",
            "train_ratio": 0.6,
            "validation_ratio": 0.2,
            "test_ratio": 0.2,
            "train_nodes": len(splits["train"]),
            "validation_nodes": len(splits["validation"]),
            "test_nodes": len(splits["test"]),
            "windows": raw_graph.get("split_dates", {}),
        },
    }
    dump(run_dir / "model_config.json", config)
    dump(
        run_dir / "preprocessing.json",
        {
            "metadata_scaler": {
                "fitted_on_split": "train",
                "train_nodes": len(splits["train"]),
                "mean": scaler.mean_.tolist(),
                "scale": scaler.scale_.tolist(),
            },
            "relation_policy": "inductive-rur-rsr-rtr-v1",
            "text": tokenizer_info,
        },
    )

    # Serving graph is strictly label-free
    serving_graph = {
        "schema_version": 1,
        "graph_schema": raw_graph["graph_schema"],
        "relation_policy": "inductive-rur-rsr-rtr-v1",
        "review_ids": review_ids,
        "x_text": x_text_cpu,
        "x_meta": x_meta_cpu,
        "edge_index_rur": edges_cpu["rur"],
        "edge_index_rsr": edges_cpu["rsr"],
        "edge_index_rtr": edges_cpu["rtr"],
    }
    torch.save(serving_graph, run_dir / "serving_graph.pt")

    # Evaluation targets stored separately
    np.savez_compressed(
        run_dir / "evaluation_targets.npz",
        labels=labels,
        train_indices=splits["train"],
        validation_indices=splits["validation"],
        test_indices=splits["test"],
    )

    # Move tensors to training device
    x_text, x_meta = x_text_cpu.to(device), x_meta_cpu.to(device)
    edges = {name: edge.to(device) for name, edge in edges_cpu.items()}
    y = torch.from_numpy(labels).long().to(device)
    split_tensors = {name: torch.from_numpy(values).long().to(device) for name, values in splits.items()}

    # Class-weighted cross entropy on train labels
    train_counts = np.bincount(labels[splits["train"]], minlength=2)
    weights = torch.tensor(train_counts.sum() / (2.0 * train_counts), dtype=torch.float32, device=device)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)

    model = RobertaRelationGNN(
        text_dim=x_text.shape[1], meta_dim=x_meta.shape[1], hidden_dim=args.hidden_dim, dropout=args.dropout
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)

    best_state, best_val_f1, best_epoch, stale = None, -1.0, -1, 0
    training_log = []

    for epoch in range(1, args.epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits = model(x_text, x_meta, edges)
        train_loss = loss_fn(logits[split_tensors["train"]], y[split_tensors["train"]])
        train_loss.backward()
        optimizer.step()

        # Validation evaluation
        model.eval()
        with torch.inference_mode():
            scores = torch.softmax(model(x_text, x_meta, edges), dim=1)[:, 1].cpu().numpy()

        val_threshold, val_f1 = select_threshold(labels[splits["validation"]], scores[splits["validation"]])
        training_log.append({
            "epoch": epoch,
            "train_loss": float(train_loss.item()),
            "validation_f1_macro": val_f1,
            "validation_threshold": val_threshold,
        })

        if val_f1 > best_val_f1 + 1e-12:
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_val_f1 = val_f1
            best_epoch = epoch
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                break

    if best_state is None:
        raise RuntimeError("No model checkpoint produced during training")

    # Load best validation checkpoint and select final threshold on validation data
    model.load_state_dict(best_state)
    model.eval()
    with torch.inference_mode():
        final_scores = torch.softmax(model(x_text, x_meta, edges), dim=1)[:, 1].cpu().numpy()

    final_threshold, final_val_f1 = select_threshold(labels[splits["validation"]], final_scores[splits["validation"]])

    # Test exactly once after threshold selection
    test_metrics = evaluate(labels[splits["test"]], final_scores[splits["test"]], final_threshold)

    torch.save({"state_dict": best_state, "model_config": config}, run_dir / "model_state.pt")
    dump(
        run_dir / "metrics.json",
        {
            "best_epoch": best_epoch,
            "best_validation_f1_macro": best_val_f1,
            "selected_validation_threshold": final_threshold,
            "validation_f1_at_selected_threshold": final_val_f1,
            "test": test_metrics,
        },
    )
    dump(run_dir / "training_log.json", {"epochs": training_log})

    # Fixed label-free reproduction record on first test arrival node
    fixed_test_index = int(splits["test"][0])
    fixed_record = {
        "review_id": review_ids[fixed_test_index],
        "node_index": fixed_test_index,
        "expected_fraud_score": float(final_scores[fixed_test_index]),
        "tolerance": 1e-6,
        "labels_required_for_reproduction": False,
    }
    dump(run_dir / "fixed_review_reproduction.json", fixed_record)

    tracked_files = [
        "model_state.pt",
        "model_config.json",
        "preprocessing.json",
        "serving_graph.pt",
        "evaluation_targets.npz",
        "metrics.json",
        "training_log.json",
        "fixed_review_reproduction.json",
    ]
    manifest = {
        "schema_version": 1,
        "bundle_type": "raw_yelpchi_inductive_roberta_gnn_v1",
        "provenance": "real_benchmark_data",
        "model_family": "raw_yelpchi_inductive_roberta_gnn_v1",
        "relation_policy": "inductive-rur-rsr-rtr-v1",
        "evaluation_protocol": "inductive_temporal_replay",
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "threshold": final_threshold,
        "metrics": {"test": test_metrics},
        "fixed_review": fixed_record,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda": getattr(torch.version, "cuda", None),
        },
        "files": {name: sha256(run_dir / name) for name in tracked_files},
    }
    dump(run_dir / "run_manifest.json", manifest)
    manifest_sha = sha256(run_dir / "run_manifest.json")

    run_record = {
        "run_id": run_id,
        "model_family": "raw_yelpchi_inductive_roberta_gnn_v1",
        "relation_policy": "inductive-rur-rsr-rtr-v1",
        "bundle_manifest_sha256": manifest_sha,
        "evaluation_protocol": config["evaluation_protocol"],
        "selected_validation_threshold": final_threshold,
        "test_metrics": test_metrics,
        "bundle_location": str(run_dir),
        "reproduction_command": f"python ml/reproduce_yelpchi_inductive_bundle.py --bundle-dir {run_dir} --manifest-sha256 {manifest_sha}",
    }
    dump(Path(args.run_record_dir).resolve() / f"{run_id}.json", run_record)

    print(json.dumps({"run_id": run_id, "bundle_dir": str(run_dir), "manifest_sha256": manifest_sha}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
