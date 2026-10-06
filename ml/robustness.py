"""
Robustness Evaluation and Adversarial Analysis for NeuroGraph-DB.
Executes Protocol A (Train Clean -> Eval Camouflage) and Protocol B (Adversarial Training).
Generates artifacts/results/robustness_summary.csv, ml/ROBUSTNESS.md, and ml/figures/*.png.
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_ml_dir = os.path.abspath(os.path.dirname(__file__))
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from ml.data import get_artifacts_dir
from ml.train import train_single_run

ALL_MODELS = ["text_only", "gnn_only", "concat", "neurograph"]
ALL_VARIANTS = [
    "clean",
    "sem_L1", "sem_L2", "sem_L3",
    "topo_p10", "topo_p30", "topo_p50", "topo_hub_p30",
    "both_L3_p30"
]
ADVERSARIAL_TRAIN_VARIANTS = ["sem_L3", "topo_p30", "both_L3_p30"]


def run_robustness_suite(
    models: list[str] | None = None,
    variants: list[str] | None = None,
    seeds: list[int] | None = None,
    epochs: int = 50,
    artifacts_dir: str | None = None,
    figures_dir: str | None = None,
) -> pd.DataFrame:
    if models is None:
        models = ALL_MODELS
    if variants is None:
        variants = ALL_VARIANTS
    if seeds is None:
        seeds = [42, 43, 44, 45, 46]
    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()
    if figures_dir is None:
        figures_dir = os.path.join(os.path.dirname(__file__), "figures")

    os.makedirs(figures_dir, exist_ok=True)
    os.makedirs(os.path.join(artifacts_dir, "results"), exist_ok=True)

    raw_results = []

    # Protocol A: Train clean, evaluate on all variants
    print("\n=======================================================")
    print("           PROTOCOL A: TRAIN CLEAN -> EVAL CAMOUFLAGE")
    print("=======================================================\n")
    for model_name in models:
        for seed in seeds:
            # We train on clean once per seed and evaluate on all variants
            print(f"--- Training {model_name} on clean (seed={seed}) ---")
            train_cfg = {"epochs": epochs, "patience": 12, "loss_type": "focal"}
            # Clean eval
            clean_res = train_single_run(
                model_name=model_name,
                train_variant="clean",
                eval_variant="clean",
                seed=seed,
                config=train_cfg,
                artifacts_dir=artifacts_dir,
            )
            raw_results.append({
                "protocol": "Protocol A",
                "model": model_name,
                "train_variant": "clean",
                "eval_variant": "clean",
                "seed": seed,
                "auc": clean_res["metrics"]["auc"],
                "f1_macro": clean_res["metrics"]["f1_macro"],
                "pr_auc": clean_res["metrics"]["pr_auc"],
            })

            # Evaluate the same trained model on all other variants
            # To evaluate cleanly with the same threshold, we call train_single_run with eval_variant
            for var in variants:
                if var == "clean":
                    continue
                var_res = train_single_run(
                    model_name=model_name,
                    train_variant="clean",
                    eval_variant=var,
                    seed=seed,
                    config=train_cfg,
                    artifacts_dir=artifacts_dir,
                )
                raw_results.append({
                    "protocol": "Protocol A",
                    "model": model_name,
                    "train_variant": "clean",
                    "eval_variant": var,
                    "seed": seed,
                    "auc": var_res["metrics"]["auc"],
                    "f1_macro": var_res["metrics"]["f1_macro"],
                    "pr_auc": var_res["metrics"]["pr_auc"],
                })

    # Protocol B: Adversarial training (Train on attacked, eval on same and clean)
    print("\n=======================================================")
    print("         PROTOCOL B: ADVERSARIAL TRAINING")
    print("=======================================================\n")
    for model_name in models:
        for adv_var in ADVERSARIAL_TRAIN_VARIANTS:
            for seed in seeds:
                print(f"--- Training {model_name} on {adv_var} (seed={seed}) ---")
                train_cfg = {"epochs": epochs, "patience": 12, "loss_type": "focal"}

                # Eval on same
                res_same = train_single_run(
                    model_name=model_name,
                    train_variant=adv_var,
                    eval_variant=adv_var,
                    seed=seed,
                    config=train_cfg,
                    artifacts_dir=artifacts_dir,
                )
                raw_results.append({
                    "protocol": "Protocol B",
                    "model": model_name,
                    "train_variant": adv_var,
                    "eval_variant": adv_var,
                    "seed": seed,
                    "auc": res_same["metrics"]["auc"],
                    "f1_macro": res_same["metrics"]["f1_macro"],
                    "pr_auc": res_same["metrics"]["pr_auc"],
                })

                # Eval on clean
                res_clean = train_single_run(
                    model_name=model_name,
                    train_variant=adv_var,
                    eval_variant="clean",
                    seed=seed,
                    config=train_cfg,
                    artifacts_dir=artifacts_dir,
                )
                raw_results.append({
                    "protocol": "Protocol B",
                    "model": model_name,
                    "train_variant": adv_var,
                    "eval_variant": "clean",
                    "seed": seed,
                    "auc": res_clean["metrics"]["auc"],
                    "f1_macro": res_clean["metrics"]["f1_macro"],
                    "pr_auc": res_clean["metrics"]["pr_auc"],
                })

    df_raw = pd.DataFrame(raw_results)

    # Calculate clean baseline metrics per model and seed to compute deltas
    clean_baselines = df_raw[
        (df_raw["protocol"] == "Protocol A") & (df_raw["eval_variant"] == "clean")
    ].set_index(["model", "seed"])[["auc", "pr_auc"]]

    def get_deltas(row):
        m, s = row["model"], row["seed"]
        if (m, s) in clean_baselines.index:
            c_auc = clean_baselines.loc[(m, s), "auc"]
            c_prauc = clean_baselines.loc[(m, s), "pr_auc"]
            delta_auc = row["auc"] - c_auc
            retention = row["pr_auc"] / max(1e-6, c_prauc)
        else:
            delta_auc = 0.0
            retention = 1.0
        return pd.Series([delta_auc, retention], index=["delta_auc_vs_clean", "pr_auc_retention"])

    deltas_df = df_raw.apply(get_deltas, axis=1)
    df_raw = pd.concat([df_raw, deltas_df], axis=1)

    # Aggregate over seeds: mean and std
    grouped = df_raw.groupby(["protocol", "model", "train_variant", "eval_variant"])
    agg_df = grouped.agg({
        "auc": ["mean", "std"],
        "f1_macro": ["mean", "std"],
        "pr_auc": ["mean", "std"],
        "delta_auc_vs_clean": ["mean", "std"],
        "pr_auc_retention": ["mean", "std"],
    }).reset_index()

    # Flatten column names for CSV export
    summary_rows = []
    for _, row in agg_df.iterrows():
        summary_rows.append({
            "protocol": row[("protocol", "")],
            "model": row[("model", "")],
            "train_variant": row[("train_variant", "")],
            "eval_variant": row[("eval_variant", "")],
            "auc": round(float(row[("auc", "mean")]), 4),
            "auc_std": round(float(row[("auc", "std")]), 4) if not pd.isna(row[("auc", "std")]) else 0.0,
            "f1_macro": round(float(row[("f1_macro", "mean")]), 4),
            "f1_macro_std": round(float(row[("f1_macro", "std")]), 4) if not pd.isna(row[("f1_macro", "std")]) else 0.0,
            "pr_auc": round(float(row[("pr_auc", "mean")]), 4),
            "pr_auc_std": round(float(row[("pr_auc", "std")]), 4) if not pd.isna(row[("pr_auc", "std")]) else 0.0,
            "delta_auc_vs_clean": round(float(row[("delta_auc_vs_clean", "mean")]), 4),
            "pr_auc_retention": round(float(row[("pr_auc_retention", "mean")]), 4),
        })

    summary_df = pd.DataFrame(summary_rows)
    csv_path = os.path.join(artifacts_dir, "results", "robustness_summary.csv")
    summary_df.to_csv(csv_path, index=False)
    print(f"\nSaved robustness summary CSV to {csv_path}")

    # Generate Figures
    generate_figures(df_raw, figures_dir)

    # Generate ROBUSTNESS.md and results_summary.md
    generate_markdown_reports(summary_df, os.path.dirname(__file__))

    return summary_df


def generate_figures(df_raw: pd.DataFrame, figures_dir: str):
    """Generates and saves publication quality figures."""
    sns.set_theme(style="whitegrid", font_scale=1.1)
    df_proto_a = df_raw[df_raw["protocol"] == "Protocol A"].copy()

    # 1. Grouped Bar Chart of PR-AUC across variants
    plt.figure(figsize=(14, 6))
    ax = sns.barplot(
        data=df_proto_a,
        x="eval_variant",
        y="pr_auc",
        hue="model",
        palette="viridis",
        errorbar="sd",
        capsize=0.08
    )
    plt.title("PR-AUC Robustness Under Semantic and Topology Camouflage (Protocol A)")
    plt.xlabel("Evaluation Camouflage Variant")
    plt.ylabel("PR-AUC")
    plt.ylim(0, 1.0)
    plt.xticks(rotation=25)
    plt.legend(title="Model Architecture", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    bar_prauc_path = os.path.join(figures_dir, "robustness_grouped_prauc.png")
    plt.savefig(bar_prauc_path, dpi=300)
    plt.close()

    # 2. Grouped Bar Chart of AUC across variants
    plt.figure(figsize=(14, 6))
    ax = sns.barplot(
        data=df_proto_a,
        x="eval_variant",
        y="auc",
        hue="model",
        palette="mako",
        errorbar="sd",
        capsize=0.08
    )
    plt.title("ROC-AUC Robustness Under Semantic and Topology Camouflage (Protocol A)")
    plt.xlabel("Evaluation Camouflage Variant")
    plt.ylabel("ROC-AUC")
    plt.ylim(0.4, 1.0)
    plt.xticks(rotation=25)
    plt.legend(title="Model Architecture", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    bar_auc_path = os.path.join(figures_dir, "robustness_grouped_auc.png")
    plt.savefig(bar_auc_path, dpi=300)
    plt.close()

    # 3. Metric Decay under Semantic Attack Progression (Clean -> L1 -> L2 -> L3)
    sem_variants = ["clean", "sem_L1", "sem_L2", "sem_L3"]
    df_sem = df_proto_a[df_proto_a["eval_variant"].isin(sem_variants)].copy()
    plt.figure(figsize=(8, 5))
    sns.lineplot(
        data=df_sem,
        x="eval_variant",
        y="pr_auc",
        hue="model",
        marker="o",
        linewidth=2.5,
        palette="tab10"
    )
    plt.title("PR-AUC Degradation under Increasing Semantic Camouflage (L1 → L3)")
    plt.xlabel("Semantic Attack Level")
    plt.ylabel("PR-AUC")
    plt.ylim(0, 1.0)
    plt.tight_layout()
    sem_path = os.path.join(figures_dir, "semantic_attack_decay.png")
    plt.savefig(sem_path, dpi=300)
    plt.close()

    # 4. Metric Decay under Topology Attack Progression (Clean -> p10 -> p30 -> p50)
    topo_variants = ["clean", "topo_p10", "topo_p30", "topo_p50"]
    df_topo = df_proto_a[df_proto_a["eval_variant"].isin(topo_variants)].copy()
    plt.figure(figsize=(8, 5))
    sns.lineplot(
        data=df_topo,
        x="eval_variant",
        y="pr_auc",
        hue="model",
        marker="s",
        linewidth=2.5,
        palette="tab10"
    )
    plt.title("PR-AUC Degradation under Topology Camouflage Edge Dilution (p10 → p50)")
    plt.xlabel("Topology Attack Level")
    plt.ylabel("PR-AUC")
    plt.ylim(0, 1.0)
    plt.tight_layout()
    topo_path = os.path.join(figures_dir, "topology_attack_decay.png")
    plt.savefig(topo_path, dpi=300)
    plt.close()

    print(f"Generated and saved all 4 plots in {figures_dir}")


def generate_markdown_reports(summary_df: pd.DataFrame, ml_dir: str):
    """Writes ml/ROBUSTNESS.md and ml/results_summary.md with formatted markdown tables."""
    # 1. ROBUSTNESS.md
    rob_md_path = os.path.join(ml_dir, "ROBUSTNESS.md")
    with open(rob_md_path, "w", encoding="utf-8") as f:
        f.write("# Robustness Evaluation & Adversarial Analysis\n\n")
        f.write("This document summarizes empirical performance across all architectures under LLM semantic camouflage and topology edge dilution attacks on YelpChi.\n\n")

        f.write("## Protocol A: Train Clean -> Evaluate under Camouflage\n\n")
        proto_a = summary_df[summary_df["protocol"] == "Protocol A"]
        f.write("| Model | Evaluation Variant | ROC-AUC | PR-AUC | F1-Macro | delta ROC-AUC | PR-AUC Retention |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for _, r in proto_a.iterrows():
            f.write(
                f"| `{r['model']}` | `{r['eval_variant']}` | "
                f"{r['auc']:.4f} +/- {r['auc_std']:.4f} | "
                f"{r['pr_auc']:.4f} +/- {r['pr_auc_std']:.4f} | "
                f"{r['f1_macro']:.4f} +/- {r['f1_macro_std']:.4f} | "
                f"{r['delta_auc_vs_clean']:+.4f} | "
                f"{r['pr_auc_retention'] * 100:.1f}% |\n"
            )

        f.write("\n## Protocol B: Adversarial Training\n\n")
        proto_b = summary_df[summary_df["protocol"] == "Protocol B"]
        f.write("| Model | Train Variant | Eval Variant | ROC-AUC | PR-AUC | F1-Macro | PR-AUC Retention |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for _, r in proto_b.iterrows():
            f.write(
                f"| `{r['model']}` | `{r['train_variant']}` | `{r['eval_variant']}` | "
                f"{r['auc']:.4f} +/- {r['auc_std']:.4f} | "
                f"{r['pr_auc']:.4f} +/- {r['pr_auc_std']:.4f} | "
                f"{r['f1_macro']:.4f} +/- {r['f1_macro_std']:.4f} | "
                f"{r['pr_auc_retention'] * 100:.1f}% |\n"
            )

        f.write("\n## Generated Visualizations\n\n")
        f.write("- **Grouped PR-AUC by Variant:** `ml/figures/robustness_grouped_prauc.png`\n")
        f.write("- **Grouped ROC-AUC by Variant:** `ml/figures/robustness_grouped_auc.png`\n")
        f.write("- **Semantic Attack Progression:** `ml/figures/semantic_attack_decay.png`\n")
        f.write("- **Topology Attack Progression:** `ml/figures/topology_attack_decay.png`\n")

    # 2. results_summary.md (Clean benchmark summary)
    res_md_path = os.path.join(ml_dir, "results_summary.md")
    with open(res_md_path, "w", encoding="utf-8") as f:
        f.write("# Benchmark Results Summary\n\n")
        f.write("Performance of all models on clean YelpChi (mean +/- std over seeds):\n\n")
        f.write("| Model Architecture | ROC-AUC | PR-AUC | F1-Macro |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        clean_recs = summary_df[
            (summary_df["protocol"] == "Protocol A") & (summary_df["eval_variant"] == "clean")
        ]
        for _, r in clean_recs.iterrows():
            f.write(
                f"| `{r['model']}` | "
                f"{r['auc']:.4f} +/- {r['auc_std']:.4f} | "
                f"{r['pr_auc']:.4f} +/- {r['pr_auc_std']:.4f} | "
                f"{r['f1_macro']:.4f} +/- {r['f1_macro_std']:.4f} |\n"
            )

    print(f"Generated {rob_md_path} and {res_md_path}")



def main():
    parser = argparse.ArgumentParser(description="Run complete robustness benchmark suite")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    parser.add_argument("--models", nargs="+", type=str, default=ALL_MODELS)
    parser.add_argument("--artifacts-dir", type=str, default=None)
    args = parser.parse_args()

    run_robustness_suite(
        models=args.models,
        seeds=args.seeds,
        epochs=args.epochs,
        artifacts_dir=args.artifacts_dir,
    )


if __name__ == "__main__":
    main()
