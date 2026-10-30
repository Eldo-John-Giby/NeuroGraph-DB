#!/usr/bin/env python3
"""Run four real-data model arms on the exact deployed temporal split.

The plan is written before training. No labels enter the input tensors. Test
labels are used only after validation checkpoint/threshold selection. A frozen
seed-42 deployed checkpoint is retained; added seeds measure training variation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score, roc_curve

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ml.models.matched_baselines import build_matched_model

RELATIONS = ("rur", "rsr", "rtr")
MODELS = ("text_only", "graph_only", "concat", "neurograph")
TITLES = {"text_only": "Text only", "graph_only": "Graph only", "concat": "Text + graph concatenation", "neurograph": "NeuroGraph"}
DESCRIPTIONS = {
    "text_only": "Frozen RoBERTa text embeddings and an MLP; no metadata or graph inputs.",
    "graph_only": "Fourteen numeric features and three GraphSAGE branches with learned global relation weights; no text embeddings.",
    "concat": "The same text and graph branches joined by concatenation; no text-conditioned relation attention or learned fusion gate.",
    "neurograph": "Deployed architecture: RoBERTa, three metadata GraphSAGE branches, text-conditioned relation attention and gated fusion.",
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def select_threshold(labels, scores):
    """Vectorized equivalent of the original 199-threshold macro-F1 search."""
    thresholds = np.linspace(0.01, 0.99, 199)
    order = np.argsort(scores, kind="stable")
    y = labels[order]
    cut = np.searchsorted(scores[order], thresholds, side="left")
    cumulative = np.r_[0, np.cumsum(y)]
    fn = cumulative[cut]
    tp = y.sum() - fn
    tn = cut - fn
    fp = len(y) - cut - tp
    positive = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(199), where=(2 * tp + fp + fn) != 0)
    negative = np.divide(2 * tn, 2 * tn + fp + fn, out=np.zeros(199), where=(2 * tn + fp + fn) != 0)
    f1 = (positive + negative) / 2
    best = int(np.argmax(f1))
    return float(thresholds[best]), float(f1[best])


def metrics(y, scores, threshold):
    predicted = scores >= threshold
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    return {"roc_auc": float(roc_auc_score(y, scores)), "pr_auc": float(average_precision_score(y, scores)),
            "f1_macro": float(f1_score(y, predicted, average="macro", zero_division=0)),
            "precision": float(precision_score(y, predicted, zero_division=0)),
            "recall": float(recall_score(y, predicted, zero_division=0)), "threshold": float(threshold),
            "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}}


def curves(y, scores):
    fpr, tpr, _ = roc_curve(y, scores)
    precision, recall, _ = precision_recall_curve(y, scores)
    # Quantile-of-index reduction preserves endpoint order for displayed traces.
    ri = np.unique(np.linspace(0, len(fpr) - 1, min(151, len(fpr))).astype(int))
    pi = np.unique(np.linspace(0, len(recall) - 1, min(151, len(recall))).astype(int))
    return {"roc": [{"x": float(fpr[i]), "y": float(tpr[i])} for i in ri],
            "pr": [{"x": float(recall[i]), "y": float(precision[i])} for i in pi[::-1]]}


def sparse_edges(graph, keep=1.0, seed=20261031):
    n = len(graph["review_ids"])
    result = {}
    generator = torch.Generator().manual_seed(seed)
    for relation in RELATIONS:
        edge = graph[f"edge_index_{relation}"]
        if keep < 1:
            edge = edge[:, torch.rand(edge.shape[1], generator=generator) < keep]
        # PyG sparse adjacency uses destination rows and source columns.
        adjacency = torch.sparse_coo_tensor(edge.flip(0), torch.ones(edge.shape[1]), (n, n)).coalesce()
        result[relation] = adjacency.to_sparse_csr()
    return result


def load_verified_inputs(bundle, source):
    manifest = json.loads((bundle / "run_manifest.json").read_text())
    for name in ("serving_graph.pt", "model_state.pt", "model_config.json", "evaluation_targets.npz", "preprocessing.json", "metrics.json"):
        if sha(bundle / name) != manifest["files"][name]:
            raise ValueError("Verified input checksum mismatch: " + name)
    graph_manifest = json.loads((bundle / "inductive_graph_manifest.json").read_text())
    if sha(source) != graph_manifest["files"]["training_csv_sha256"]:
        raise ValueError("Raw source does not match training CSV fingerprint")
    graph = torch.load(bundle / "serving_graph.pt", map_location="cpu", weights_only=False)
    if any(k in graph for k in ("labels", "y", "ground_truth_label")):
        raise ValueError("Serving inputs must be label-free")
    with np.load(bundle / "evaluation_targets.npz", allow_pickle=False) as targets:
        labels = targets["labels"].copy()
        splits = {s: targets[s + "_indices"].copy() for s in ("train", "validation", "test")}
    n = len(graph["review_ids"])
    if n != 47176 or graph["x_meta"].shape != (n, 14) or graph["x_text"].shape != (n, 768):
        raise ValueError("Unexpected dataset dimensions")
    if len(set(graph["review_ids"])) != n or not np.array_equal(np.concatenate(list(splits.values())), np.arange(n)):
        raise ValueError("Node identities or chronological split membership invalid")
    for r in RELATIONS:
        src, dst = graph["edge_index_" + r]
        if not bool(torch.all(src < dst)):
            raise ValueError("Noncausal graph edge: " + r)
        if int(torch.bincount(dst, minlength=n).max()) > 50:
            raise ValueError("Neighbor cap exceeded")
    preprocessing = json.loads((bundle / "preprocessing.json").read_text())
    if preprocessing["metadata_scaler"]["fitted_on_split"] != "train":
        raise ValueError("Scaler must be fitted on train only")
    return graph, labels, splits, manifest, graph_manifest


def run_arm(variant, seed, args, graph, labels, splits, edges):
    target = args.output / f"{variant}_seed{seed}"
    if (target / "manifest.json").is_file():
        old = json.loads((target / "manifest.json").read_text())
        if old.get("protocol_sha256") != sha(args.output / "protocol.json"):
            raise ValueError("Cannot resume a different protocol")
        for name, expected in old["files"].items():
            if sha(target / name) != expected:
                raise ValueError("Existing run file changed: " + name)
        print(f"RESUME {variant} seed={seed}", flush=True)
        return json.loads((target / "result.json").read_text())
    target.mkdir(parents=True, exist_ok=True)
    np.random.seed(seed)
    torch.manual_seed(seed)
    model = build_matched_model(variant, text_dim=768, meta_dim=14, hidden_dim=128, dropout=0.2)
    x_text, x_meta = graph["x_text"], graph["x_meta"]
    idx = {k: torch.from_numpy(v).long() for k, v in splits.items()}
    y = torch.from_numpy(labels).long()
    counts = np.bincount(labels[splits["train"]], minlength=2)
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(counts.sum() / (2 * counts), dtype=torch.float32))
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    started = time.monotonic()
    reused = variant == "neurograph" and seed == 42
    if reused:
        checkpoint = torch.load(args.bundle / "model_state.pt", map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["state_dict"])
        history = json.loads((args.bundle / "training_log.json").read_text())["epochs"]
        source_metrics = json.loads((args.bundle / "metrics.json").read_text())
        best_epoch = source_metrics["best_epoch"]
    else:
        best_f1, best_epoch, stale, best_state = -1.0, -1, 0, None
        history = []
        for epoch in range(1, 81):
            model.train()
            optimizer.zero_grad(set_to_none=True)
            logits = model(x_text, x_meta, edges)
            loss = loss_fn(logits[idx["train"]], y[idx["train"]])
            loss.backward()
            optimizer.step()
            del logits
            model.eval()
            with torch.inference_mode():
                scores = torch.softmax(model(x_text, x_meta, edges), dim=1)[:, 1].numpy()
            threshold, vf1 = select_threshold(labels[splits["validation"]], scores[splits["validation"]])
            history.append({"epoch": epoch, "train_loss": float(loss), "validation_f1_macro": vf1, "validation_threshold": threshold})
            if vf1 > best_f1 + 1e-12:
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
                best_f1, best_epoch, stale = vf1, epoch, 0
            else:
                stale += 1
            if epoch == 1 or epoch % 5 == 0 or stale >= 12:
                print(f"TRAIN {variant} seed={seed} epoch={epoch} val_macro_f1={vf1:.5f} best_epoch={best_epoch} elapsed={time.monotonic()-started:.1f}s", flush=True)
            if stale >= 12:
                break
        model.load_state_dict(best_state)
    model.eval()
    with torch.inference_mode():
        scores = torch.softmax(model(x_text, x_meta, edges), dim=1)[:, 1].numpy()
    # Lock checkpoint and validation threshold before calculating test metrics.
    threshold, vf1 = select_threshold(labels[splits["validation"]], scores[splits["validation"]])
    save(target / "selection.json", {"best_epoch": best_epoch, "threshold": threshold, "validation_f1_macro": vf1, "test_used_for_selection": False})
    test_scores, test_y = scores[splits["test"]], labels[splits["test"]]
    test = metrics(test_y, test_scores, threshold)
    if reused:
        for metric in ("roc_auc", "pr_auc", "f1_macro", "threshold"):
            if abs(test[metric] - source_metrics["test"][metric]) > 1e-6:
                raise ValueError("Deployed checkpoint reproduction differs: " + metric)
    result = {"model": variant, "title": TITLES[variant], "seed": seed, "best_epoch": best_epoch,
              "epochs_completed": len(history), "trainable_parameters": sum(p.numel() for p in model.parameters()),
              "reused_deployed_checkpoint": reused, "validation_f1_macro": vf1, "test": test,
              "curves": curves(test_y, test_scores), "elapsed_seconds": time.monotonic() - started,
              "environment": {"python": platform.python_version(), "torch": str(torch.__version__), "device": "cpu"},
              "context_stress": []}
    # Fixed, label-blind edge removal tests missing-context sensitivity. No retuning.
    for fraction in (0.1, 0.3, 0.5):
        stressed = sparse_edges(graph, keep=1-fraction)
        with torch.inference_mode():
            stressed_scores = torch.softmax(model(x_text, x_meta, stressed), dim=1)[:, 1].numpy()[splits["test"]]
        result["context_stress"].append({"removed_fraction": fraction, "test": metrics(test_y, stressed_scores, threshold)})
        del stressed
    torch.save({"state_dict": model.state_dict(), "model": variant, "seed": seed}, target / "checkpoint.pt")
    np.savez_compressed(target / "predictions.npz", labels=test_y, scores=test_scores, indices=splits["test"],
                        validation_scores=scores[splits["validation"]], validation_indices=splits["validation"])
    save(target / "training_log.json", {"epochs": history})
    save(target / "result.json", result)
    save(target / "manifest.json", {"protocol_sha256": sha(args.output / "protocol.json"),
         "files": {name: sha(target / name) for name in ("checkpoint.pt", "predictions.npz", "selection.json", "training_log.json", "result.json")}})
    print(f"DONE {variant} seed={seed} test={json.dumps(test)}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=ROOT / "artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z")
    parser.add_argument("--source", type=Path, default=ROOT / ".kaggle/yelpchi-raw/training_data.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/matched_benchmark/temporal_v1")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    graph, labels, splits, manifest, graph_manifest = load_verified_inputs(args.bundle, args.source)
    args.output.mkdir(parents=True, exist_ok=True)
    plan_path = args.output / "protocol.json"
    if not plan_path.exists():
        save(plan_path, {"protocol_id": "yelpchi-temporal-matched-v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset": "samygithub/collective-opinion-spam-detection/training_data.csv", "source_sha256": sha(args.source),
            "source_run": manifest["run_id"], "source_manifest_sha256": sha(args.bundle / "run_manifest.json"),
            "serving_graph_sha256": sha(args.bundle / "serving_graph.pt"),
            "evaluation_targets_sha256": sha(args.bundle / "evaluation_targets.npz"),
            "node_identity_sha256": hashlib.sha256(json.dumps(graph["review_ids"], separators=(",", ":")).encode()).hexdigest(),
            "split_counts": {s: len(i) for s, i in splits.items()}, "split_windows": graph_manifest["splits"]["windows"],
            "class_counts": {s: {"nonspam": int((labels[i]==0).sum()), "spam": int((labels[i]==1).sum())} for s, i in splits.items()},
            "feature_names": graph_manifest["feature_names"], "relations": graph_manifest["relations"],
            "edge_counts": graph_manifest["edge_counts"], "models": DESCRIPTIONS, "seeds": args.seeds,
            "training": {"optimizer": "AdamW", "learning_rate": 0.001, "weight_decay": 0.0001, "hidden_dim": 128,
                "dropout": 0.2, "max_epochs": 80, "patience": 12, "loss": "train-class-weighted cross entropy",
                "checkpoint_selection": "validation macro F1", "threshold_grid": {"min": 0.01, "max": 0.99, "count": 199},
                "test_used_for_selection": False, "scaler_fit": "train only", "text_encoder": manifest["config"]["tokenizer"],
                "seed42_neurograph": "Original sealed deployed checkpoint, no retraining or test-based replacement"},
            "stress_test": {"name": "Missing graph context", "edge_drop_fractions": [0.1, 0.3, 0.5], "seed": 20261031,
                "label_blind": True, "threshold_retuned": False, "scope": "Edge removal sensitivity; not a validated adversarial or LLM camouflage test"},
            "code_sha256": {name: sha(ROOT / name) for name in ("ml/benchmark_matched.py", "ml/models/matched_baselines.py", "ml/models/roberta_relation_gnn.py")},
            "limitations": ["Retrospective comparison on the existing chronological holdout, not a new independent dataset.",
                "Three seeds vary initialization, not dataset membership; standard deviation is not a confidence interval.",
                "Seed-42 deployed model was originally GPU-trained; added runs train on CPU with the same optimization settings.",
                "Architecture ablations change inputs and parameter counts; they do not compare all published fraud detectors.",
                "Yelp filtering labels are imperfect; performance on unlabelled user files or other domains is unmeasured."]})
    plan = json.loads(plan_path.read_text())
    for name, expected in plan["code_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("Training code changed after protocol was recorded: " + name)
    if plan["seeds"] != args.seeds:
        raise ValueError("Seed list differs from recorded protocol")
    edges = sparse_edges(graph)
    results = []
    # Reproduce the original first, so a mismatch aborts before costly training.
    jobs = [(model, seed) for model in args.models for seed in args.seeds]
    jobs.sort(key=lambda job: 0 if job == ("neurograph", 42) else 1)
    for variant, seed in jobs:
        results.append(run_arm(variant, seed, args, graph, labels, splits, edges))
    summaries = []
    for variant in args.models:
        runs = sorted([r for r in results if r["model"] == variant], key=lambda r: r["seed"])
        summaries.append({"id": variant, "name": TITLES[variant], "description": DESCRIPTIONS[variant], "runs": runs,
            "aggregate": {metric: {"mean": float(np.mean([r["test"][metric] for r in runs])),
                "std": float(np.std([r["test"][metric] for r in runs], ddof=1)) if len(runs)>1 else 0.0}
                for metric in ("roc_auc", "pr_auc", "f1_macro", "precision", "recall")}})
    report = {"schema_version": 1, "protocol": plan, "protocol_sha256": sha(plan_path),
              "generated_at": datetime.now(timezone.utc).isoformat(), "models": summaries,
              "artifact_manifests": {f"{m}_seed{s}": sha(args.output / f"{m}_seed{s}/manifest.json") for m, s in jobs}}
    save(args.output / "report.json", report)
    print(json.dumps({"report": str(args.output / 'report.json'), "models": [{"id": m['id'], "aggregate": m['aggregate']} for m in summaries]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
