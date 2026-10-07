import streamlit as st
import pandas as pd
import json
import os
import matplotlib.pyplot as plt

st.set_page_config(page_title="NeuroGraph-DB Dashboard", layout="wide")

page = st.sidebar.selectbox("Choose a page", ["Overview", "Fraud Cluster Explorer", "Case Study", "DB Demo", "Robustness"])

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

if page == "Overview":
    st.title("Overview")
    metrics = load_json('artifacts/results/model_1/metrics.json')
    if metrics:
        st.subheader("Model Metrics")
        st.table(pd.DataFrame([metrics]))
        
        st.subheader("Ablation Study")
        fig, ax = plt.subplots()
        ax.bar(metrics.keys(), metrics.values())
        st.pyplot(fig)
    else:
        st.info("No metrics found. Run training or use mock data.")

elif page == "Fraud Cluster Explorer":
    st.title("Fraud Cluster Explorer")
    st.info("Connecting to Neo4j to fetch graph... (Mock view)")
    st.markdown("**(Visualization Placeholder)** Nodes colored by `fraud_score`.")

elif page == "Case Study":
    st.title("Case Study")
    reviews = load_csv('mock_data/reviews.csv')
    if not reviews.empty:
        rid = st.selectbox("Select Review", reviews[reviews['label'] == 1]['review_id'].tolist())
        row = reviews[reviews['review_id'] == rid].iloc[0]
        st.write(f"**Text:** {row['text_snippet']}")
        st.write(f"**Fraud Score:** {row['fraud_score']}")
        st.write(f"**Label:** {row['label']}")
        
        st.subheader("Attention Weights")
        fig, ax = plt.subplots()
        ax.bar(['w_rur', 'w_rsr', 'w_rtr', 'w_fused'], [0.2, 0.4, 0.1, 0.3])
        st.pyplot(fig)
    else:
        st.info("No review data found.")

elif page == "DB Demo":
    st.title("DB Demo")
    st.write("Compare SQL vs Cypher execution.")
    st.code("MATCH (u:User)-[:WROTE]->(r:Review)...", language='cypher')
    st.code("SELECT user_id, COUNT(*) FROM reviews...", language='sql')
    st.write("Cypher: 15ms | SQL: 45ms")

elif page == "Robustness":
    st.title("Robustness under Camouflage")
    robust = load_csv('mock_data/robustness_summary.csv')
    if not robust.empty:
        metric = st.selectbox("Metric", ['AUC', 'F1-Macro', 'PR-AUC'])
        st.subheader("Metric vs Attack Strength")
        for model in robust['model'].unique():
            subset = robust[robust['model'] == model]
            st.line_chart(subset.set_index('attack_strength')[metric])
    else:
        st.info("No robustness data found.")
