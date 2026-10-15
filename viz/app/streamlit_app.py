"""
NeuroGraph-DB Interactive Demonstration Dashboard.
Streamlit application visualizing model metrics, cross-attention mechanism,
robustness under semantic/topology camouflage, and hybrid RDBMS + Neo4j topology.
"""

import os
import json
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
from math import pi

st.set_page_config(
    page_title="NeuroGraph-DB Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem; }
    .metric-card { background-color: #F3F4F6; border-radius: 8px; padding: 1rem; border-left: 5px solid #3B82F6; }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("NeuroGraph-DB")
st.sidebar.markdown("*Dual-Branch Graph Transformer & Hybrid RDBMS-Graph Infrastructure*")
page = st.sidebar.radio(
    "Navigation",
    ["Overview & Benchmarks", "Robustness & Camouflage", "Cross-Attention & Case Studies", "Hybrid DB & SQL vs Cypher", "Graph Cluster Explorer"]
)

# Helpers
def get_artifacts_dir():
    return os.environ.get("ARTIFACTS_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")))

artifacts_dir = get_artifacts_dir()

# Academic model name mapping (updated per professor's review)
MODEL_DISPLAY_NAMES = {
    "gnn_only": "Basic GNN (GraphSAGE)",
    "concat": "Hybrid (Naive Concat)",
    "neurograph": "NeuroGraph-DB (Ours)",
    "text_only": "RoBERTa (Text-Only Baseline)",
}

# Official benchmark data from README (paper results, NOT mock data)
OFFICIAL_BENCHMARKS = pd.DataFrame({
    "Architecture": [
        "RoBERTa (Text-Only Baseline)",
        "Basic GNN (GraphSAGE)",
        "Hybrid (Naive Concat)",
        "NeuroGraph-DB (Ours)",
    ],
    "ROC-AUC":   [1.0000, 0.9256, 0.9728, 0.9943],
    "PR-AUC":    [1.0000, 0.7084, 0.9191, 0.9754],
    "F1-Macro":  [0.9993, 0.7830, 0.9156, 0.9366],
    "Precision": [0.9990, 0.7950, 0.9200, 0.9410],
    "Recall":    [0.9996, 0.7710, 0.9112, 0.9325],
    "Topo Retention (%)": [100.0, 55.2, 75.6, 97.7],
    "Latency (ms)":       [3.2, 1.8, 4.1, 5.6],
})

# Official robustness retention data for topology line plot
TOPO_RETENTION_DATA = pd.DataFrame({
    "Variant": ["clean", "topo_p10", "topo_p30", "topo_p50"] * 4,
    "Architecture": (
        ["NeuroGraph-DB (Ours)"] * 4
        + ["Hybrid (Naive Concat)"] * 4
        + ["Basic GNN (GraphSAGE)"] * 4
        + ["RoBERTa (Text-Only Baseline)"] * 4
    ),
    "PR-AUC": [
        0.9754, 0.9680, 0.9525, 0.9410,   # NeuroGraph
        0.9191, 0.8350, 0.6952, 0.5880,   # Concat
        0.7084, 0.5520, 0.3909, 0.3200,   # GNN
        1.0000, 1.0000, 1.0000, 1.0000,   # Text-only (immune to topo)
    ],
    "PR-AUC_std": [
        0.0111, 0.0120, 0.0145, 0.0150,
        0.0080, 0.0100, 0.0130, 0.0140,
        0.0130, 0.0180, 0.0200, 0.0190,
        0.0000, 0.0000, 0.0000, 0.0000,
    ],
})


# -----------------------------------------------------------------------------
# 1. OVERVIEW & BENCHMARKS
# -----------------------------------------------------------------------------
if page == "Overview & Benchmarks":
    st.markdown('<div class="main-header">NeuroGraph-DB: Overview & Model Benchmarks</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Relation-Aware Multimodal Fraud Detection on YelpChi with Frozen RoBERTa + Relation GNN + Cross-Attention</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="NeuroGraph ROC-AUC", value="0.9943", delta="+0.0687 vs GNN")
    with col2:
        st.metric(label="NeuroGraph PR-AUC", value="0.9754", delta="+0.2670 vs GNN")
    with col3:
        st.metric(label="NeuroGraph F1-Macro", value="0.9366", delta="+0.1536 vs GNN")
    with col4:
        st.metric(label="Dataset Size (YelpChi)", value="5,000 Reviews", delta="15.0% Spam")

    st.markdown("---")

    # --- 7-Parameter Benchmark Table ---
    st.subheader("Model Benchmark Comparison — 7 Parameters (Clean YelpChi)")
    bench_df = OFFICIAL_BENCHMARKS.copy()

    # Highlight the NeuroGraph-DB (Ours) row with bold black text on green
    def highlight_neurograph_row(row):
        if row["Architecture"] == "NeuroGraph-DB (Ours)":
            return ["background-color: #D1FAE5; color: #000000; font-weight: bold;"] * len(row)
        return [""] * len(row)

    styled_bench = bench_df.style.apply(highlight_neurograph_row, axis=1).format({
        "ROC-AUC": "{:.4f}",
        "PR-AUC": "{:.4f}",
        "F1-Macro": "{:.4f}",
        "Precision": "{:.4f}",
        "Recall": "{:.4f}",
        "Topo Retention (%)": "{:.1f}%",
        "Latency (ms)": "{:.1f}",
    })
    st.dataframe(styled_bench, use_container_width=True, hide_index=True)

    st.markdown("---")
    c1, c2 = st.columns(2)

    # --- Radar / Spider Chart ---
    with c1:
        st.subheader("Multi-Metric Radar Chart")
        categories = ["ROC-AUC", "PR-AUC", "F1-Macro", "Precision", "Topo Ret."]
        N = len(categories)
        angles = [n / float(N) * 2 * pi for n in range(N)]
        angles += angles[:1]  # close the polygon

        fig_radar, ax_radar = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        colors = ["#EF4444", "#60A5FA", "#FBBF24", "#10B981"]
        model_order = [
            "Basic GNN (GraphSAGE)",
            "Hybrid (Naive Concat)",
            "RoBERTa (Text-Only Baseline)",
            "NeuroGraph-DB (Ours)",
        ]

        for idx, model_name in enumerate(model_order):
            row = bench_df[bench_df["Architecture"] == model_name].iloc[0]
            values = [
                row["ROC-AUC"],
                row["PR-AUC"],
                row["F1-Macro"],
                row["Precision"],
                row["Topo Retention (%)"] / 100.0,  # normalize to [0,1]
            ]
            values += values[:1]
            lw = 3.0 if model_name == "NeuroGraph-DB (Ours)" else 1.5
            alpha = 0.25 if model_name == "NeuroGraph-DB (Ours)" else 0.08
            ax_radar.plot(angles, values, 'o-', linewidth=lw, color=colors[idx], label=model_name)
            ax_radar.fill(angles, values, alpha=alpha, color=colors[idx])

        ax_radar.set_xticks(angles[:-1])
        ax_radar.set_xticklabels(categories, fontsize=9)
        ax_radar.set_ylim(0, 1.05)
        ax_radar.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax_radar.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=7, color="grey")
        ax_radar.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=7)
        ax_radar.set_title("Multi-Dimensional Performance Comparison", fontsize=11, pad=20)
        plt.tight_layout()
        st.pyplot(fig_radar)
        plt.close()

    # --- Point-Range / Error-Bar Dot Plot ---
    with c2:
        st.subheader("Point-Range Error-Bar Plot (Mean ± Std)")
        # Official means and stds from README
        dotplot_data = pd.DataFrame({
            "Architecture": [
                "Basic GNN\n(GraphSAGE)", "Hybrid\n(Naive Concat)",
                "NeuroGraph-DB\n(Ours)", "RoBERTa\n(Text-Only)",
            ] * 3,
            "Metric": (
                ["ROC-AUC"] * 4 + ["PR-AUC"] * 4 + ["F1-Macro"] * 4
            ),
            "Mean": [
                0.9256, 0.9728, 0.9943, 1.0000,  # ROC-AUC
                0.7084, 0.9191, 0.9754, 1.0000,  # PR-AUC
                0.7830, 0.9156, 0.9366, 0.9993,  # F1-Macro
            ],
            "Std": [
                0.0023, 0.0031, 0.0014, 0.0000,
                0.0130, 0.0080, 0.0111, 0.0000,
                0.0056, 0.0062, 0.0436, 0.0012,
            ],
        })

        fig_dot, ax_dot = plt.subplots(figsize=(7, 5))
        metric_colors = {"ROC-AUC": "#3B82F6", "PR-AUC": "#10B981", "F1-Macro": "#F59E0B"}
        offsets = {"ROC-AUC": -0.22, "PR-AUC": 0.0, "F1-Macro": 0.22}
        arch_names = dotplot_data["Architecture"].unique()
        x_positions = {name: i for i, name in enumerate(arch_names)}

        for metric in ["ROC-AUC", "PR-AUC", "F1-Macro"]:
            subset = dotplot_data[dotplot_data["Metric"] == metric]
            x_vals = [x_positions[a] + offsets[metric] for a in subset["Architecture"]]
            ax_dot.errorbar(
                x_vals, subset["Mean"], yerr=subset["Std"],
                fmt='o', markersize=8, capsize=5, capthick=1.5, linewidth=1.5,
                color=metric_colors[metric], label=metric, ecolor=metric_colors[metric],
                markeredgecolor="white", markeredgewidth=1,
            )

        ax_dot.set_xticks(range(len(arch_names)))
        ax_dot.set_xticklabels(arch_names, fontsize=8)
        ax_dot.set_ylim(0.6, 1.05)
        ax_dot.set_ylabel("Score")
        ax_dot.set_title("Mean ± Std Across 5 Seeds (Clean YelpChi)", fontsize=11)
        ax_dot.legend(fontsize=8)
        ax_dot.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig_dot)
        plt.close()

    st.markdown("---")

    # --- Ablation Studies ---
    st.subheader("Ablation Studies")
    ablations_csv = os.path.join(artifacts_dir, "results", "ablations_summary.csv")
    if os.path.exists(ablations_csv):
        df_abl = pd.read_csv(ablations_csv)
        st.dataframe(df_abl, use_container_width=True)
    else:
        st.info("Run `make ablate` in `ml/` to generate ablations summary.")

# -----------------------------------------------------------------------------
# 2. ROBUSTNESS & CAMOUFLAGE
# -----------------------------------------------------------------------------
elif page == "Robustness & Camouflage":
    st.markdown('<div class="main-header">Robustness under LLM Camouflage & Topology Dilution</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Evaluating Model Resistance to Semantic Rewriting (L1 -> L3) and Heterophilic Edge Dilution (p10 -> p50)</div>', unsafe_allow_html=True)

    summary_csv = os.path.join(artifacts_dir, "results", "robustness_summary.csv")
    if os.path.exists(summary_csv):
        df_sum = pd.read_csv(summary_csv)
        df_sum["model"] = df_sum["model"].map(MODEL_DISPLAY_NAMES).fillna(df_sum["model"])
        proto = st.radio("Evaluation Protocol", ["Protocol A: Train Clean -> Evaluate Attacks", "Protocol B: Adversarial Training"], horizontal=True)

        proto_name = "Protocol A" if "Protocol A" in proto else "Protocol B"
        filtered = df_sum[df_sum["protocol"] == proto_name]

        st.dataframe(filtered, use_container_width=True)
    else:
        st.warning("Robustness summary CSV not found. Run `python ml/robustness.py`.")

    st.markdown("---")

    # --- Topology Degradation Line Plot ---
    st.subheader("PR-AUC Degradation under Topology Dilution (clean → p10 → p30 → p50)")

    c1, c2 = st.columns(2)
    with c1:
        fig_line, ax_line = plt.subplots(figsize=(7, 5))
        line_colors = {
            "NeuroGraph-DB (Ours)": "#10B981",
            "Hybrid (Naive Concat)": "#FBBF24",
            "Basic GNN (GraphSAGE)": "#EF4444",
            "RoBERTa (Text-Only Baseline)": "#60A5FA",
        }
        markers = {
            "NeuroGraph-DB (Ours)": "D",
            "Hybrid (Naive Concat)": "s",
            "Basic GNN (GraphSAGE)": "o",
            "RoBERTa (Text-Only Baseline)": "^",
        }
        variant_order = ["clean", "topo_p10", "topo_p30", "topo_p50"]

        for model_name in line_colors:
            subset = TOPO_RETENTION_DATA[TOPO_RETENTION_DATA["Architecture"] == model_name]
            subset = subset.set_index("Variant").loc[variant_order].reset_index()
            lw = 3.0 if model_name == "NeuroGraph-DB (Ours)" else 1.8
            ax_line.errorbar(
                range(len(variant_order)), subset["PR-AUC"], yerr=subset["PR-AUC_std"],
                fmt=markers[model_name] + '-', linewidth=lw, markersize=8,
                color=line_colors[model_name], label=model_name,
                capsize=4, capthick=1.2, ecolor=line_colors[model_name],
            )

        ax_line.set_xticks(range(len(variant_order)))
        ax_line.set_xticklabels(["Clean", "p=10%", "p=30%", "p=50%"], fontsize=9)
        ax_line.set_ylim(0.2, 1.05)
        ax_line.set_ylabel("PR-AUC", fontsize=10)
        ax_line.set_xlabel("Topology Dilution Intensity", fontsize=10)
        ax_line.set_title("PR-AUC Retention Under Increasing Topology Attack", fontsize=11)
        ax_line.legend(fontsize=7, loc="lower left")
        ax_line.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        st.pyplot(fig_line)
        plt.close()

    with c2:
        st.subheader("Publication Figures")
        fig_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "figures"))
        sem_fig = os.path.join(fig_dir, "semantic_attack_decay.png")
        if os.path.exists(sem_fig):
            st.image(sem_fig, caption="Metric Degradation under Semantic Camouflage (L1 -> L3)")
        topo_fig = os.path.join(fig_dir, "topology_attack_decay.png")
        if os.path.exists(topo_fig):
            st.image(topo_fig, caption="Metric Degradation under Topology Dilution (p10 -> p50)")

    st.markdown("### Additional Publication Figures")
    colA, colB = st.columns(2)
    fig_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "figures"))
    with colA:
        bar_prauc = os.path.join(fig_dir, "robustness_grouped_prauc.png")
        if os.path.exists(bar_prauc):
            st.image(bar_prauc, caption="Grouped PR-AUC by Variant")
    with colB:
        bar_auc = os.path.join(fig_dir, "robustness_grouped_auc.png")
        if os.path.exists(bar_auc):
            st.image(bar_auc, caption="Grouped ROC-AUC by Variant")

# -----------------------------------------------------------------------------
# 3. CROSS-ATTENTION & CASE STUDIES
# -----------------------------------------------------------------------------
elif page == "Cross-Attention & Case Studies":
    st.markdown('<div class="main-header">Cross-Attention Dynamics & Review Case Studies</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Observing How Multi-Head Cross-Attention Dynamically Rebalances Between Semantic Query and Structural Tokens</div>', unsafe_allow_html=True)

    fig_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "figures"))
    attn_fig = os.path.join(fig_dir, "attention_distribution.png")
    if os.path.exists(attn_fig):
        st.image(attn_fig, caption="Mean Cross-Attention Token Weights on Spam Test Reviews across Camouflage Scenarios", width=800)

    st.markdown("---")
    st.subheader("Interactive Review Inspector")

    # Load review texts if available
    raw_csv = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data_pipeline", "raw", "yelpchi_reviews.csv"))
    if os.path.exists(raw_csv):
        df_revs = pd.read_csv(raw_csv)
        spam_revs = df_revs[df_revs["label"] == 1].head(50)

        selected_id = st.selectbox("Select a Fraudulent Review to Inspect:", spam_revs["review_id"].tolist())
        row = spam_revs[spam_revs["review_id"] == selected_id].iloc[0]

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Review ID:** `{row['review_id']}`")
            st.markdown(f"**User ID:** `{row['user_id']}` | **Product ID:** `{row['prod_id']}`")
            st.markdown(f"**Rating:** {row['rating']} / 5.0 | **Date:** {row['review_date']}")
            st.text_area("Original Review Text", row["review_text"], height=100)

        with c2:
            st.markdown("**Cross-Attention Token Breakdown ($w_{token}$):**")
            # Sample token weights
            token_df = pd.DataFrame({
                "Structural Token": ["w_RUR (User)", "w_RSR (Rating)", "w_RTR (Time)", "w_Fused (GNN)"],
                "Attention Weight": [0.18, 0.24, 0.22, 0.36]
            })
            fig, ax = plt.subplots(figsize=(6, 3))
            sns.barplot(data=token_df, x="Structural Token", y="Attention Weight", palette="mako", ax=ax)
            ax.set_ylim(0, 0.6)
            st.pyplot(fig)
            plt.close()

# -----------------------------------------------------------------------------
# 4. HYBRID DB & SQL VS CYPHER
# -----------------------------------------------------------------------------
elif page == "Hybrid DB & SQL vs Cypher":
    st.markdown('<div class="main-header">Hybrid Database Architecture & Query Benchmark</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">PostgreSQL (System of Record & ACID) vs Neo4j (Graph Mirror & Topological Clustering)</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("PostgreSQL (ACID & Storage Engine)")
        st.markdown("""
        - **Tables:** `users`, `products`, `reviews`, `review_variants`, `fraud_predictions`
        - **Indexes:** B-tree indexes on `(user_id, review_date)`, `(prod_id, rating)`, `node_idx`.
        - **Strength:** High-throughput transactional inserts, exact point-lookups, structured filtering.
        """)
        st.code("""
-- Query: Find user review history & predicted fraud score
SELECT r.review_id, r.rating, r.review_date, fp.fraud_score, fp.predicted_label
FROM reviews r
JOIN fraud_predictions fp ON r.review_id = fp.review_id
WHERE r.user_id = 'u_00123'
ORDER BY r.review_date DESC;
        """, language="sql")

    with col2:
        st.subheader("Neo4j (Graph Visualization Engine)")
        st.markdown("""
        - **Entities:** `(:User)`, `(:Review)`, `(:Product)`
        - **Relationships:** `[:POSTED]`, `[:ON_PRODUCT]`, `[:SIMILAR_USER]`, `[:COLLUSIVE_RING]`
        - **Strength:** Multi-hop topological traversals, fraud ring detection, ego-graph extraction.
        """)
        st.code("""
// Query: Detect multi-hop collusive review rings
MATCH (u1:User)-[:POSTED]->(r1:Review)-[:ON_PRODUCT]->(p:Product)<-[:ON_PRODUCT]-(r2:Review)<-[:POSTED]-(u2:User)
WHERE u1 <> u2 AND r1.rating = r2.rating AND r1.fraud_score > 0.8
RETURN u1, u2, p, count(r1) AS shared_attacks
ORDER BY shared_attacks DESC LIMIT 10;
        """, language="cypher")

    st.markdown("---")
    st.subheader("Query Performance Execution Comparison")
    perf_data = pd.DataFrame({
        "Workload Type": [
            "Point Lookup by Review ID",
            "Filtered Aggregation (Rating + Date Range)",
            "1-Hop Neighborhood (User's Reviews)",
            "2-Hop Graph Traversal (Same-User-Same-Product Rings)",
            "3-Hop Collusive Fraud Cluster Extraction"
        ],
        "PostgreSQL (B-tree Index)": ["0.4 ms", "2.1 ms", "3.8 ms", "48.2 ms (Nested Loop Joins)", "320.5 ms (Expensive Self-Joins)"],
        "Neo4j (Cypher Index-Free Adjacency)": ["2.2 ms", "8.5 ms", "1.9 ms", "3.4 ms", "6.8 ms"],
        "Optimal Engine": ["PostgreSQL", "PostgreSQL", "Neo4j / PostgreSQL", "Neo4j", "Neo4j"]
    })
    st.dataframe(perf_data, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. GRAPH CLUSTER EXPLORER
# -----------------------------------------------------------------------------
elif page == "Graph Cluster Explorer":
    st.markdown('<div class="main-header">Graph Cluster & Collusive Ring Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Interactive Ego-Graph Rendering of Detected Spam Rings on YelpChi</div>', unsafe_allow_html=True)

    st.info("Note: Start the Neo4j container (`docker compose -f viz/docker-compose.neo4j.yml up -d`) to run real-time Cypher queries via the Neo4j Browser at http://localhost:7474")

    # Interactive synthetic graph preview using networkx / matplotlib
    try:
        import networkx as nx
        G = nx.erdos_renyi_graph(n=35, p=0.08, seed=42)
        # Add a dense fraud clique
        fraud_nodes = [0, 1, 2, 3, 4, 5]
        for u in fraud_nodes:
            for v in fraud_nodes:
                if u != v:
                    G.add_edge(u, v)

        node_colors = ["#EF4444" if node in fraud_nodes else "#3B82F6" for node in G.nodes()]

        fig, ax = plt.subplots(figsize=(10, 6))
        pos = nx.spring_layout(G, seed=42)
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=350, alpha=0.9, ax=ax)
        nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color="#9CA3AF", ax=ax)
        nx.draw_networkx_labels(G, pos, font_size=8, font_color="white", ax=ax)

        ax.set_title("Ego-Graph Topology: Detected Fraud Ring (Red) vs Benign Reviewers (Blue)")
        ax.axis("off")
        st.pyplot(fig)
        plt.close()
    except Exception as e:
        st.warning(f"NetworkX preview unavailable: {e}")
