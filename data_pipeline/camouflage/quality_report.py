"""
Generates quality report and statistics for semantic and topology camouflage attacks.
Writes data_pipeline/camouflage/QUALITY.md.
"""

import os
import pandas as pd
import numpy as np


def generate_quality_report():
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")))
    camo_dir = os.path.join(artifacts_dir, "camouflage")
    quality_md_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "QUALITY.md"))

    sem_stats = []
    for lvl in ["L1", "L2", "L3"]:
        var_name = f"sem_{lvl}"
        pq_path = os.path.join(camo_dir, f"texts_{var_name}.parquet")
        if os.path.exists(pq_path):
            df = pd.read_parquet(pq_path)
            sims = df["cosine_sim"].values
            sem_stats.append({
                "Variant": var_name,
                "Sample Count": len(df),
                "Mean Cosine Sim": float(np.mean(sims)),
                "Std Cosine Sim": float(np.std(sims)),
                "Min Sim": float(np.min(sims)),
                "Max Sim": float(np.max(sims)),
            })

    topo_stats = []
    for var_name in ["topo_p10", "topo_p30", "topo_p50", "topo_hub_p30"]:
        csv_path = os.path.join(camo_dir, f"edges_added_{var_name}.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            rel_counts = df["relation"].value_counts().to_dict()
            topo_stats.append({
                "Variant": var_name,
                "Total Edges Added": len(df),
                "RUR Added": rel_counts.get("rur", 0),
                "RSR Added": rel_counts.get("rsr", 0),
                "RTR Added": rel_counts.get("rtr", 0),
            })

    with open(quality_md_path, "w", encoding="utf-8") as f:
        f.write("# Camouflage Quality & Attack Verification Report\n\n")
        f.write("This report details the quantitative properties of the LLM semantic and topological camouflage attacks generated on the YelpChi dataset.\n\n")

        f.write("## 1. Semantic Camouflage Fidelity & Shift\n\n")
        f.write("| Variant | Review Count | Mean Cosine Sim | Std Cosine Sim | Min Sim | Max Sim |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for s in sem_stats:
            f.write(f"| `{s['Variant']}` | {s['Sample Count']} | {s['Mean Cosine Sim']:.4f} | {s['Std Cosine Sim']:.4f} | {s['Min Sim']:.4f} | {s['Max Sim']:.4f} |\n")

        f.write("\n## 2. Topological Camouflage Edge Dilution\n\n")
        f.write("| Variant | Total Heterophilic Edges Added | RUR Added | RSR Added | RTR Added |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for t in topo_stats:
            f.write(f"| `{t['Variant']}` | {t['Total Edges Added']} | {t['RUR Added']} | {t['RSR Added']} | {t['RTR Added']} |\n")

    print(f"Generated quality report at {quality_md_path}")


if __name__ == "__main__":
    generate_quality_report()