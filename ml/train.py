"""
Training and Evaluation Pipeline for NeuroGraph-DB.
Handles class imbalance (Focal Loss, Weighted CE), early stopping on Val PR-AUC,
reproducible seed setting, model checkpointing, and metric logging.
"""

import os
import sys
import time
import json
import argparse
import datetime

import yaml
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

# Ensure repo root and ml dir are in sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_ml_dir = os.path.abspath(os.path.dirname(__file__))
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from ml.data import load_variant, graph_dict_to_batch, get_artifacts_dir, RelationGraphBatch
from ml.models import build_model
from ml.evaluate import find_best_threshold_on_val, evaluate_predictions, save_metrics_json



def set_seed(seed: int):
    """Sets random seeds for complete reproducibility."""
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class FocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.75, gamma: float = 2.0, reduction: str = "mean"):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = F.softmax(logits, dim=-1)
        targets_one_hot = F.one_hot(targets, num_classes=logits.shape[-1]).float()
        pt = (probs * targets_one_hot).sum(dim=-1)  # prob of true class
        # Weight for class 1 vs 0
        weights = torch.where(targets == 1, self.alpha, 1.0 - self.alpha)
        focal_weight = weights * ((1.0 - pt) ** self.gamma)
        ce_loss = F.cross_entropy(logits, targets, reduction="none")
        loss = focal_weight * ce_loss
        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        return loss


def get_loss_fn(loss_type: str, y_train: torch.Tensor, alpha: float = 0.75, gamma: float = 2.0):
    if loss_type == "focal":
        return FocalLoss(alpha=alpha, gamma=gamma)
    elif loss_type == "weighted_ce":
        n_pos = (y_train == 1).sum().item()
        n_neg = (y_train == 0).sum().item()
        weight = torch.tensor([1.0, float(n_neg) / max(1, n_pos)], dtype=torch.float32)
        return nn.CrossEntropyLoss(weight=weight)
    else:
        return nn.CrossEntropyLoss()


def forward_batch(
    model: nn.Module,
    batch: RelationGraphBatch,
    model_name: str,
    return_attention: bool = False
):
    """Unified forward dispatcher across model architectures."""
    if model_name == "text_only":
        return model(x_sem=batch.x_sem, return_attention=return_attention)
    elif model_name == "gnn_only":
        return model(
            x_meta=batch.x_meta,
            edge_index_dict=batch.edge_index_dict,
            x_sem=batch.x_sem,
            return_attention=return_attention
        )
    elif model_name == "concat":
        return model(
            x_sem=batch.x_sem,
            x_meta=batch.x_meta,
            edge_index_dict=batch.edge_index_dict,
            return_attention=return_attention
        )
    elif model_name == "neurograph":
        return model(
            x_sem=batch.x_sem,
            x_meta=batch.x_meta,
            edge_index_dict=batch.edge_index_dict,
            return_attention=return_attention
        )
    else:
        raise ValueError(f"Unknown model architecture {model_name}")


def train_single_run(
    model_name: str = "neurograph",
    train_variant: str = "clean",
    eval_variant: str = "clean",
    seed: int = 42,
    config: dict | None = None,
    artifacts_dir: str | None = None,
    device: str | None = None,
    save_artifacts: bool = True,
) -> dict:
    """Executes a single train/eval run with exact contract logging."""
    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()

    if config is None:
        config = {}

    set_seed(seed)
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    dev = torch.device(device)

    # 1. Load Data
    train_dict = load_variant(train_variant, artifacts_dir=artifacts_dir)
    train_batch = graph_dict_to_batch(train_dict).to(dev)

    if eval_variant == train_variant:
        eval_batch = train_batch
        eval_dict = train_dict
    else:
        eval_dict = load_variant(eval_variant, artifacts_dir=artifacts_dir)
        eval_batch = graph_dict_to_batch(eval_dict).to(dev)

    # 2. Build Model
    model = build_model(
        model_name=model_name,
        sem_dim=config.get("sem_dim", 768),
        meta_dim=config.get("meta_dim", train_batch.x_meta.shape[1]),
        d_model=config.get("d_model", 128),
        num_heads=config.get("num_heads", 4),
        dropout=config.get("dropout", 0.2),
        use_sem_in_gnn=config.get("use_sem_in_gnn", False),
        relations=tuple(config.get("relations", ["rur", "rsr", "rtr"])),
    ).to(dev)

    # 3. Setup Optimizer and Loss
    lr = config.get("lr", 0.001)
    weight_decay = config.get("weight_decay", 1e-4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    loss_type = config.get("loss_type", "focal")
    loss_fn = get_loss_fn(
        loss_type,
        train_batch.y[train_batch.train_mask].cpu(),
        alpha=config.get("focal_alpha", 0.75),
        gamma=config.get("focal_gamma", 2.0)
    ).to(dev)

    epochs = config.get("epochs", 60)
    patience = config.get("patience", 15)

    best_val_pr_auc = -1.0
    best_weights = None
    patience_counter = 0

    # 4. Training Loop
    tr_mask = train_batch.train_mask
    va_mask = train_batch.val_mask
    y_tr = train_batch.y[tr_mask]
    y_va_np = train_batch.y[va_mask].cpu().numpy()

    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()

        out = forward_batch(model, train_batch, model_name, return_attention=False)
        logits_tr = out[tr_mask] if isinstance(out, torch.Tensor) else out[0][tr_mask]
        loss = loss_fn(logits_tr, y_tr)
        loss.backward()
        optimizer.step()

        # Validation step
        model.eval()
        with torch.no_grad():
            val_out = forward_batch(model, train_batch, model_name, return_attention=False)
            val_logits = val_out[va_mask] if isinstance(val_out, torch.Tensor) else val_out[0][va_mask]
            val_probs = F.softmax(val_logits, dim=-1)[:, 1].cpu().numpy()

            val_metrics = evaluate_predictions(y_va_np, val_probs, threshold=0.5)
            val_pr_auc = val_metrics["pr_auc"]

            if val_pr_auc > best_val_pr_auc:
                best_val_pr_auc = val_pr_auc
                best_weights = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break

    # Restore best checkpoint
    if best_weights is not None:
        model.load_state_dict({k: v.to(dev) for k, v in best_weights.items()})

    # 5. Threshold Selection on TRAIN variant validation split
    model.eval()
    with torch.no_grad():
        val_out = forward_batch(model, train_batch, model_name, return_attention=False)
        val_logits = val_out[va_mask] if isinstance(val_out, torch.Tensor) else val_out[0][va_mask]
        val_probs = F.softmax(val_logits, dim=-1)[:, 1].cpu().numpy()
        best_threshold = find_best_threshold_on_val(y_va_np, val_probs)

    # 6. Final Evaluation on EVAL variant test split using TRAIN threshold
    with torch.no_grad():
        if model_name == "neurograph":
            eval_out, attn_weights = forward_batch(model, eval_batch, model_name, return_attention=True)
        else:
            eval_out = forward_batch(model, eval_batch, model_name, return_attention=False)
            attn_weights = None

        all_logits = eval_out if isinstance(eval_out, torch.Tensor) else eval_out[0]
        all_probs = F.softmax(all_logits, dim=-1)[:, 1].cpu().numpy()

        te_mask = eval_batch.test_mask
        y_te_np = eval_batch.y[te_mask].cpu().numpy()
        te_probs = all_probs[te_mask.cpu().numpy()]

        test_metrics = evaluate_predictions(y_te_np, te_probs, threshold=best_threshold)

    # Build Run ID
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    run_id = f"{model_name}_{train_variant}_{eval_variant}_{seed}_{timestamp}"

    final_metrics = {
        "model": model_name,
        "seed": seed,
        "train_variant": train_variant,
        "eval_variant": eval_variant,
        "auc": test_metrics["auc"],
        "f1_macro": test_metrics["f1_macro"],
        "pr_auc": test_metrics["pr_auc"],
        "threshold": best_threshold,
        "run_id": run_id,
    }

    if save_artifacts:
        # Save metrics.json
        save_metrics_json(final_metrics, run_id, artifacts_dir=artifacts_dir)

        # Save attention.parquet if applicable
        if attn_weights is not None:
            w_np = attn_weights.cpu().numpy()
            n_nodes = w_np.shape[0]
            rel_list = list(config.get("relations", ["rur", "rsr", "rtr"]))
            attn_dict = {"node_idx": np.arange(n_nodes)}
            for i, rel in enumerate(rel_list):
                attn_dict[f"w_{rel}"] = w_np[:, i]
            attn_dict["w_fused"] = w_np[:, -1]
            attn_df = pd.DataFrame(attn_dict)
            run_dir = os.path.join(artifacts_dir, "results", run_id)
            os.makedirs(run_dir, exist_ok=True)
            attn_df.to_parquet(os.path.join(run_dir, "attention.parquet"), index=False)


        # Save predictions parquet
        pred_labels = (all_probs >= best_threshold).astype(int)
        splits = []
        for i in range(len(all_probs)):
            if eval_batch.train_mask[i]:
                splits.append("train")
            elif eval_batch.val_mask[i]:
                splits.append("val")
            else:
                splits.append("test")

        df_pred = pd.DataFrame({
            "review_id": eval_dict["review_ids"],
            "node_idx": np.arange(len(all_probs)),
            "fraud_score": all_probs.astype(float),
            "predicted_label": pred_labels,
            "split": splits,
            "variant": eval_variant,
        })
        pred_path = os.path.join(artifacts_dir, "predictions", f"{run_id}.parquet")
        df_pred.to_parquet(pred_path, index=False)

    return {
        "metrics": final_metrics,
        "model": model,
        "run_id": run_id,
        "probs": all_probs,
        "threshold": best_threshold
    }


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate NeuroGraph-DB models")
    parser.add_argument("--model", type=str, default="neurograph",
                        choices=["text_only", "gnn_only", "concat", "neurograph"])
    parser.add_argument("--train-variant", type=str, default="clean")
    parser.add_argument("--eval-variant", type=str, default="clean")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--loss-type", type=str, default=None)
    parser.add_argument("--artifacts-dir", type=str, default=None)
    parser.add_argument("--to-postgres", action="store_true", help="Upsert predictions to PostgreSQL")

    args = parser.parse_args()

    cfg = {}
    if args.config and os.path.exists(args.config):
        with open(args.config, "r") as f:
            cfg = yaml.safe_load(f)
    else:
        # Load model default yaml if exists
        default_cfg_path = os.path.join(os.path.dirname(__file__), "configs", f"{args.model}.yaml")
        if os.path.exists(default_cfg_path):
            with open(default_cfg_path, "r") as f:
                cfg = yaml.safe_load(f)

    if args.epochs is not None:
        cfg["epochs"] = args.epochs
    if args.lr is not None:
        cfg["lr"] = args.lr
    if args.loss_type is not None:
        cfg["loss_type"] = args.loss_type

    print(f"Starting run: model={args.model}, train={args.train_variant}, eval={args.eval_variant}, seed={args.seed}")
    res = train_single_run(
        model_name=args.model,
        train_variant=args.train_variant,
        eval_variant=args.eval_variant,
        seed=args.seed,
        config=cfg,
        artifacts_dir=args.artifacts_dir,
    )
    print("Run completed successfully!")
    print(json.dumps(res["metrics"], indent=2))

    if args.to_postgres:
        from ml.export_predictions import export_run_to_postgres
        print(f"Upserting predictions to Postgres for run_id={res['run_id']}...")
        export_run_to_postgres(res["run_id"], artifacts_dir=args.artifacts_dir)


if __name__ == "__main__":
    main()
