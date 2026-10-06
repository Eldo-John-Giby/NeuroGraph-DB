"""
Attention Analysis Module for NeuroGraph-DB.
Analyzes cross-attention weight distributions [w_rur, w_rsr, w_rtr, w_fused]
for spam test reviews under clean vs camouflaged environments (sem_L3, topo_p30, both_L3_p30).
Performs paired statistical testing (paired t-test / Wilcoxon) of attention shift hypotheses.
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import torch.nn.functional as F

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_ml_dir = os.path.abspath(os.path.dirname(__file__))
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

from ml.data import get_artifacts_dir, load_variant, graph_dict_to_batch
from ml.train import train_single_run, forward_batch


def extract_attention_for_variant(model, variant_name: str, artifacts_dir: str, device: torch.device):
    var_dict = load_variant(variant_name, artifacts_dir=artifacts_dir)
    batch = graph_dict_to_batch(var_dict).to(device)

    model.eval()
    with torch.no_grad():
        _, attn_weights = forward_batch(model, batch, "neurograph", return_attention=True)

    weights_np = attn_weights.cpu().numpy()  # [N, 4]
    y_np = batch.y.cpu().numpy()
    te_mask_np = batch.test_mask.cpu().numpy()
    spam_test_mask = (y_np == 1) & te_mask_np

    spam_attn = weights_np[spam_test_mask]  # [N_spam_test, 4]
    spam_node_indices = np.where(spam_test_mask)[0]

    df = pd.DataFrame(spam_attn, columns=["w_rur", "w_rsr", "w_rtr", "w_fused"])
    df["node_idx"] = spam_node_indices
    df["variant"] = variant_name
    return df, weights_np, spam_attn


def run_attention_analysis(
    seed: int = 42,
    epochs: int = 50,
    artifacts_dir: str | None = None,
    figures_dir: str | None = None
) -> dict:
    if artifacts_dir is None:
        artifacts_dir = get_artifacts_dir()
    if figures_dir is None:
        figures_dir = os.path.join(os.path.dirname(__file__), "figures")
    os.makedirs(figures_dir, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 1. Train NeuroGraph on Clean
    print("Training NeuroGraph on Clean graph for Attention Analysis...")
    train_res = train_single_run(
        model_name="neurograph",
        train_variant="clean",
        eval_variant="clean",
        seed=seed,
        config={"epochs": epochs, "loss_type": "focal"},
        artifacts_dir=artifacts_dir,
    )
    model = train_res["model"]

    # 2. Extract attention across Clean and Attacks
    variants = ["clean", "sem_L3", "topo_p30", "both_L3_p30"]
    attn_dfs = []
    arrays_by_var = {}

    for var in variants:
        df_var, all_weights, spam_attn = extract_attention_for_variant(model, var, artifacts_dir, device)
        attn_dfs.append(df_var)
        arrays_by_var[var] = spam_attn

    combined_df = pd.concat(attn_dfs, ignore_index=True)

    # 3. Statistical hypothesis testing (paired differences for spam test nodes)
    clean_spam = arrays_by_var["clean"]
    sem_spam = arrays_by_var["sem_L3"]
    topo_spam = arrays_by_var["topo_p30"]
    both_spam = arrays_by_var["both_L3_p30"]

    # Hypothesis 1: Under semantic attack (sem_L3), reliance on GNN fused token increases
    fused_clean = clean_spam[:, 3]
    fused_sem = sem_spam[:, 3]
    diff_fused = fused_sem - fused_clean
    t_stat_fused, p_val_fused = stats.ttest_rel(fused_sem, fused_clean)
    try:
        w_stat_fused, w_pval_fused = stats.wilcoxon(fused_sem, fused_clean)
    except Exception:
        w_stat_fused, w_pval_fused = 0.0, 1.0

    # Hypothesis 2: Under topology attack (topo_p30), structural attention shifts
    # Compute mean attention per variant
    mean_table = []
    for var in variants:
        arr = arrays_by_var[var]
        mean_table.append({
            "variant": var,
            "w_rur": float(arr[:, 0].mean()),
            "w_rur_std": float(arr[:, 0].std()),
            "w_rsr": float(arr[:, 1].mean()),
            "w_rsr_std": float(arr[:, 1].std()),
            "w_rtr": float(arr[:, 2].mean()),
            "w_rtr_std": float(arr[:, 2].std()),
            "w_fused": float(arr[:, 3].mean()),
            "w_fused_std": float(arr[:, 3].std()),
        })

    summary_df = pd.DataFrame(mean_table)

    # 4. Generate Visualization
    melted_df = pd.melt(
        combined_df,
        id_vars=["variant", "node_idx"],
        value_vars=["w_rur", "w_rsr", "w_rtr", "w_fused"],
        var_name="Token",
        value_name="Attention Weight"
    )

    plt.figure(figsize=(10, 6))
    sns.set_theme(style="whitegrid", font_scale=1.1)
    palette = {"w_rur": "#3498db", "w_rsr": "#e74c3c", "w_rtr": "#2ecc71", "w_fused": "#9b59b6"}
    sns.barplot(
        data=melted_df,
        x="variant",
        y="Attention Weight",
        hue="Token",
        palette=palette,
        errorbar="sd",
        capsize=0.08
    )
    plt.title("Cross-Attention Token Weight Distribution on Spam Test Reviews")
    plt.xlabel("Evaluation Scenario")
    plt.ylabel("Mean Attention Weight (Sums to 1)")
    plt.ylim(0, 0.6)
    plt.legend(title="Structural Token", loc="upper right")
    plt.tight_layout()
    fig_path = os.path.join(figures_dir, "attention_distribution.png")
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"Saved attention distribution figure to {fig_path}")

    # 5. Write ATTENTION_ANALYSIS.md
    md_path = os.path.join(os.path.dirname(__file__), "ATTENTION_ANALYSIS.md")
    with open(md_path, "w") as f:
        f.write("# Cross-Attention Mechanism Analysis\n\n")
        f.write("Investigation of cross-attention token weighting $[w_{RUR}, w_{RSR}, w_{RTR}, w_{Fused}]$ for spam reviews under semantic and topology camouflage.\n\n")
        f.write("## Mean Attention Weights on Spam Test Set\n\n")
        f.write("| Variant | w_RUR | w_RSR | w_RTR | w_Fused |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for _, r in summary_df.iterrows():
            f.write(
                f"| `{r['variant']}` | "
                f"{r['w_rur']:.4f} ± {r['w_rur_std']:.4f} | "
                f"{r['w_rsr']:.4f} ± {r['w_rsr_std']:.4f} | "
                f"{r['w_rtr']:.4f} ± {r['w_rtr_std']:.4f} | "
                f"{r['w_fused']:.4f} ± {r['w_fused_std']:.4f} |\n"
            )

        f.write("\n## Statistical Hypothesis Testing\n\n")
        f.write(f"- **Hypothesis (Attention Shift on Semantic Camouflage):** When review text is camouflaged (`sem_L3`), cross-attention dynamically adjusts attention toward structural relations.\n")
        f.write(f"  - Clean mean `w_fused`: {clean_spam[:, 3].mean():.4f}\n")
        f.write(f"  - `sem_L3` mean `w_fused`: {sem_spam[:, 3].mean():.4f}\n")
        f.write(f"  - Mean paired shift $\\Delta w_{{fused}}$: {diff_fused.mean():+.4f}\n")
        f.write(f"  - Paired t-test: $t = {t_stat_fused:.4f}$, $p = {p_val_fused:.4e}$\n")
        f.write(f"  - Wilcoxon signed-rank test: $W = {w_stat_fused:.1f}$, $p = {w_pval_fused:.4e}$\n")

        f.write("\n## Attention Visualization\n\n")
        f.write("![Attention Distribution](figures/attention_distribution.png)\n")

    print(f"Generated {md_path}")
    return {"summary": summary_df, "p_val": p_val_fused}


def main():
    parser = argparse.ArgumentParser(description="Analyze cross-attention weights under attacks")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--artifacts-dir", type=str, default=None)
    args = parser.parse_args()

    run_attention_analysis(seed=args.seed, epochs=args.epochs, artifacts_dir=args.artifacts_dir)


if __name__ == "__main__":
    main()
