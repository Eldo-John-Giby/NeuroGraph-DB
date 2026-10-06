"""
Ablation Studies Module for NeuroGraph-DB.
Systematically evaluates architectural components:
- Text ablation (no-text)
- Graph ablation (no-graph)
- Fusion strategy (concat vs cross-attention)
- Individual relation removal (no-RUR, no-RSR, no-RTR)
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_ml_dir = os.path.abspath(os.path.dirname(__file__))
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from ml.data import get_artifacts_dir
from ml.train import train_single_run


def run_ablations(
    seeds: list[int] | None = None,
    epochs: int = 50,
    artifacts_dir: str | None = None
) -> pd.DataFrame:
    if seeds is None:
        seeds = [42, 43, 44, 45, 46]
    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()

    ablation_experiments = [
        {
            "name": "Full NeuroGraph (All Relations + Cross-Attn)",
            "model": "neurograph",
            "config": {"relations": ["rur", "rsr", "rtr"], "epochs": epochs, "loss_type": "focal"}
        },
        {
            "name": "No-Text (GNN-Only)",
            "model": "gnn_only",
            "config": {"relations": ["rur", "rsr", "rtr"], "epochs": epochs, "loss_type": "focal"}
        },
        {
            "name": "No-Graph (Text-Only MLP)",
            "model": "text_only",
            "config": {"epochs": epochs, "loss_type": "focal"}
        },
        {
            "name": "Naive Concat Fusion (Concat instead of Cross-Attn)",
            "model": "concat",
            "config": {"relations": ["rur", "rsr", "rtr"], "epochs": epochs, "loss_type": "focal"}
        },
        {
            "name": "No RUR (Remove Review-User-Review)",
            "model": "neurograph",
            "config": {"relations": ["rsr", "rtr"], "epochs": epochs, "loss_type": "focal"}
        },
        {
            "name": "No RSR (Remove Review-Star-Review)",
            "model": "neurograph",
            "config": {"relations": ["rur", "rtr"], "epochs": epochs, "loss_type": "focal"}
        },
        {
            "name": "No RTR (Remove Review-Time-Review)",
            "model": "neurograph",
            "config": {"relations": ["rur", "rsr"], "epochs": epochs, "loss_type": "focal"}
        },
    ]

    all_records = []
    print("\n=======================================================")
    print("             RUNNING ABLATION STUDIES")
    print("=======================================================\n")

    for exp in ablation_experiments:
        exp_name = exp["name"]
        m_name = exp["model"]
        cfg = exp["config"]
        print(f"\n--- Running Ablation: {exp_name} ---")

        for seed in seeds:
            res = train_single_run(
                model_name=m_name,
                train_variant="clean",
                eval_variant="clean",
                seed=seed,
                config=cfg,
                artifacts_dir=artifacts_dir,
                save_artifacts=True
            )
            all_records.append({
                "experiment": exp_name,
                "model": m_name,
                "seed": seed,
                "auc": res["metrics"]["auc"],
                "f1_macro": res["metrics"]["f1_macro"],
                "pr_auc": res["metrics"]["pr_auc"],
            })

    df_raw = pd.DataFrame(all_records)
    grouped = df_raw.groupby("experiment").agg({
        "auc": ["mean", "std"],
        "f1_macro": ["mean", "std"],
        "pr_auc": ["mean", "std"],
    }).reset_index()

    summary_rows = []
    for _, row in grouped.iterrows():
        summary_rows.append({
            "experiment": row[("experiment", "")],
            "auc": round(float(row[("auc", "mean")]), 4),
            "auc_std": round(float(row[("auc", "std")]), 4) if not pd.isna(row[("auc", "std")]) else 0.0,
            "f1_macro": round(float(row[("f1_macro", "mean")]), 4),
            "f1_macro_std": round(float(row[("f1_macro", "std")]), 4) if not pd.isna(row[("f1_macro", "std")]) else 0.0,
            "pr_auc": round(float(row[("pr_auc", "mean")]), 4),
            "pr_auc_std": round(float(row[("pr_auc", "std")]), 4) if not pd.isna(row[("pr_auc", "std")]) else 0.0,
        })

    summary_df = pd.DataFrame(summary_rows)
    # Sort with Full NeuroGraph on top
    summary_df["is_full"] = summary_df["experiment"].str.startswith("Full NeuroGraph")
    summary_df = summary_df.sort_values(by=["is_full", "pr_auc"], ascending=[False, False]).drop(columns=["is_full"])

    # Save to artifacts
    csv_path = os.path.join(artifacts_dir, "results", "ablations_summary.csv")
    summary_df.to_csv(csv_path, index=False)
    print(f"Saved ablations summary to {csv_path}")

    # Write ml/ABLATIONS.md
    abl_md_path = os.path.join(os.path.dirname(__file__), "ABLATIONS.md")
    with open(abl_md_path, "w") as f:
        f.write("# Ablation Studies Summary\n\n")
        f.write("Systematic architectural ablation on YelpChi (mean ± std over 5 seeds):\n\n")
        f.write("| Ablation Setting | ROC-AUC | PR-AUC | F1-Macro |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for _, r in summary_df.iterrows():
            f.write(
                f"| **{r['experiment']}** | "
                f"{r['auc']:.4f} ± {r['auc_std']:.4f} | "
                f"{r['pr_auc']:.4f} ± {r['pr_auc_std']:.4f} | "
                f"{r['f1_macro']:.4f} ± {r['f1_macro_std']:.4f} |\n"
            )

    print(f"Generated {abl_md_path}")
    return summary_df


def main():
    parser = argparse.ArgumentParser(description="Run ablation experiments for NeuroGraph-DB")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    parser.add_argument("--artifacts-dir", type=str, default=None)
    args = parser.parse_args()

    run_ablations(seeds=args.seeds, epochs=args.epochs, artifacts_dir=args.artifacts_dir)


if __name__ == "__main__":
    main()
