#!/usr/bin/env python3
"""Train a RoBERTa + PyG model on 47,176 labelled raw YelpChi reviews.

The CSV test file is excluded because it has no labels.  This trainer creates
one deterministic 60/20/20 stratified node split from training_data.csv.
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
from ml.train_yelpchi_multimodal import embed_text, evaluate, seed_everything, select_threshold, sha256, split_nodes


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-graph-dir", required=True, help="Output directory from build_yelpchi_raw_graph.py")
    parser.add_argument("--expected-node-count", type=int, default=47176)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-record-dir", required=True)
    parser.add_argument("--roberta-model", default="FacebookAI/roberta-base")
    parser.add_argument("--roberta-revision", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--dropout", type=float, default=.2)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--text-batch-size", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    raw_dir = Path(args.raw_graph_dir).resolve()
    manifest_path, graph_path = raw_dir / "graph_manifest.json", raw_dir / "raw_graph.pt"
    graph_manifest = json.loads(manifest_path.read_text())
    if graph_manifest.get("bundle_type") != "raw_yelpchi_multimodal_graph" or graph_manifest["files"].get("raw_graph_sha256") != sha256(graph_path):
        raise ValueError("raw graph manifest does not authenticate graph artifact")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for multimodal training")
    device = torch.device(args.device)
    seed_everything(args.seed)
    raw_graph = torch.load(graph_path, map_location="cpu", weights_only=False)
    review_ids, review_texts = raw_graph["review_ids"], raw_graph["review_text"]
    x_meta_original, labels = raw_graph["x_meta"].numpy(), raw_graph["labels"].numpy().astype(np.int64)
    if len(review_ids) != len(review_texts) or len(labels) != len(review_ids) or set(np.unique(labels)) != {0, 1}:
        raise ValueError("raw graph node identity, text, and labels are invalid")
    if len(review_ids) != args.expected_node_count:
        raise ValueError(f"expected {args.expected_node_count} labelled nodes, found {len(review_ids)}")
    splits = split_nodes(labels, args.seed)
    scaler = StandardScaler().fit(x_meta_original[splits["train"]])
    x_meta_cpu = torch.from_numpy(scaler.transform(x_meta_original).astype(np.float32))
    x_text_cpu, tokenizer = embed_text(review_texts, args.roberta_model, args.roberta_revision, args.text_batch_size, args.max_length, device)
    edges_cpu = {name: raw_graph[f"edge_index_{name}"].long().contiguous() for name in ("rur", "rsr", "rtr")}
    run_id = f"raw_yelpchi_multimodal_seed{args.seed}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = Path(args.output_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    config = {"schema_version": 1, "architecture": "frozen_roberta_relation_specific_pyg_graphsage_cross_attention", "text_dim": int(x_text_cpu.shape[1]), "meta_dim": int(x_meta_cpu.shape[1]), "hidden_dim": args.hidden_dim, "dropout": args.dropout, "relations": ["rur", "rsr", "rtr"], "tokenizer": tokenizer, "raw_graph_manifest_sha256": sha256(manifest_path), "raw_graph_sha256": sha256(graph_path), "seed": args.seed, "labelled_node_count": len(review_ids), "split": {"method": "StratifiedShuffleSplit", "train": .6, "validation": .2, "test": .2, "seed": args.seed}, "evaluation_protocol": "transductive_known_node"}
    dump(run_dir / "model_config.json", config)
    dump(run_dir / "preprocessing.json", {"metadata_scaler": {"fitted_on_split": "train", "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}, "text": tokenizer})
    serving_graph = {"schema_version": 1, "graph_schema": raw_graph["graph_schema"], "review_ids": review_ids, "x_text": x_text_cpu, "x_meta": x_meta_cpu, **{f"edge_index_{name}": edge for name, edge in edges_cpu.items()}}
    torch.save(serving_graph, run_dir / "serving_graph.pt")
    np.savez_compressed(run_dir / "evaluation_targets.npz", labels=labels, **{f"{name}_indices": values for name, values in splits.items()})
    x_text, x_meta = x_text_cpu.to(device), x_meta_cpu.to(device)
    edges, y = {name: edge.to(device) for name, edge in edges_cpu.items()}, torch.from_numpy(labels).long().to(device)
    split_tensors = {name: torch.from_numpy(values).long().to(device) for name, values in splits.items()}
    counts = np.bincount(labels[splits["train"]], minlength=2)
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(counts.sum() / (2 * counts), dtype=torch.float32, device=device))
    model = RobertaRelationGNN(text_dim=x_text.shape[1], meta_dim=x_meta.shape[1], hidden_dim=args.hidden_dim, dropout=args.dropout).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    best_state, best_f1, best_epoch, stale, log = None, -1., -1, 0, []
    for epoch in range(1, args.epochs + 1):
        model.train(); optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(model(x_text, x_meta, edges)[split_tensors["train"]], y[split_tensors["train"]]); loss.backward(); optimizer.step()
        model.eval()
        with torch.inference_mode(): scores = torch.softmax(model(x_text, x_meta, edges), dim=1)[:, 1].cpu().numpy()
        threshold, val_f1 = select_threshold(labels[splits["validation"]], scores[splits["validation"]])
        log.append({"epoch": epoch, "train_loss": float(loss.item()), "validation_f1_macro": val_f1, "validation_threshold": threshold})
        if val_f1 > best_f1 + 1e-12: best_state, best_f1, best_epoch, stale = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}, val_f1, epoch, 0
        else:
            stale += 1
            if stale >= args.patience: break
    if best_state is None: raise RuntimeError("no checkpoint produced")
    model.load_state_dict(best_state); model.eval()
    with torch.inference_mode(): scores = torch.softmax(model(x_text, x_meta, edges), dim=1)[:, 1].cpu().numpy()
    threshold, validation_f1 = select_threshold(labels[splits["validation"]], scores[splits["validation"]])
    test_metrics = evaluate(labels[splits["test"]], scores[splits["test"]], threshold)
    torch.save({"state_dict": best_state, "model_config": config}, run_dir / "model_state.pt")
    dump(run_dir / "metrics.json", {"best_epoch": best_epoch, "best_validation_f1_macro": best_f1, "selected_validation_threshold": threshold, "validation_f1_at_selected_threshold": validation_f1, "test": test_metrics})
    dump(run_dir / "training_log.json", {"epochs": log})
    fixed_index = int(splits["test"][0])
    fixed = {"review_id": review_ids[fixed_index], "node_index": fixed_index, "expected_fraud_score": float(scores[fixed_index]), "tolerance": 1e-6, "labels_required_for_reproduction": False}
    dump(run_dir / "fixed_review_reproduction.json", fixed)
    tracked = ["model_state.pt", "model_config.json", "preprocessing.json", "serving_graph.pt", "evaluation_targets.npz", "metrics.json", "training_log.json", "fixed_review_reproduction.json"]
    manifest = {"schema_version": 1, "bundle_type": "raw_yelpchi_multimodal_roberta_pyg_gnn", "provenance": "real_benchmark_data", "model_claim": "Raw YelpChi review graph; frozen RoBERTa embeddings with RUR/RSR/RTR PyG GraphSAGE fusion", "run_id": run_id, "created_at_utc": datetime.now(timezone.utc).isoformat(), "config": config, "threshold": threshold, "metrics": {"test": test_metrics}, "fixed_review": fixed, "environment": {"python": sys.version, "platform": platform.platform(), "torch": torch.__version__, "cuda": torch.version.cuda}, "files": {name: sha256(run_dir / name) for name in tracked}}
    dump(run_dir / "run_manifest.json", manifest)
    manifest_sha = sha256(run_dir / "run_manifest.json")
    record = {"run_id": run_id, "bundle_manifest_sha256": manifest_sha, "model_claim": manifest["model_claim"], "evaluation_protocol": config["evaluation_protocol"], "selected_validation_threshold": threshold, "test_metrics": test_metrics, "bundle_location": str(run_dir), "reproduction_command": f"python ml/reproduce_yelpchi_multimodal_bundle.py --bundle-dir {run_dir} --manifest-sha256 {manifest_sha}"}
    dump(Path(args.run_record_dir).resolve() / f"{run_id}.json", record)
    print(json.dumps({"run_id": run_id, "bundle_dir": str(run_dir), "manifest_sha256": manifest_sha}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
