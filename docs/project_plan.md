# NeuroGraph-DB: Updated Project Plan

## Project Overview

- **Project Title:** NeuroGraph-DB: A Dual-Branch Graph Transformer with Hybrid RDBMS-Graph Infrastructure for Camouflaged Review Spam Detection
- **Course Details:** Database Systems | D2 + TD2
- **Target Publication:** IEEE ICCDS 2026 (Rajalakshmi Engineering College, Chennai)

---

## Research Objective & Gap

- **Refined Objective:** To develop and evaluate NeuroGraph-DB, a relation-aware multimodal fraud-detection framework that jointly models RoBERTa-derived review semantics and heterogeneous user–product–review relationships through multi-head cross-attention, with systematic evaluation under LLM-generated semantic and topology camouflage.
- **Research Gap Addressed:** Standard Graph Neural Network (GNN) detectors fail against modern LLM-generated fake reviews that employ "fraud camouflage" (posting benign reviews across random products) to manipulate graph topology, while current systems treat text analysis, graph learning, and enterprise database management in silos.

---

## System Architecture & Methodology

### 1. Machine Learning Core (PyTorch Geometric)
- **Semantic Branch (Transformer):** Converts review text into static 768-dimensional vector representations ($H_{sem}$) offline using pre-trained `roberta-base` to optimize compute efficiency.
- **Structural Branch (Relation-Aware GNN):** Models multi-relational graph topology ($R_{RUR}$ for Reviewer-User-Reviewer, $R_{RSR}$ for Review-Same Rating-Review, and $R_{RTR}$ for Review-Temporal-Review) in PyTorch Geometric ($H_{struc}$).
- **Cross-Modal Attention Fusion:** Applies Multi-Head Cross-Attention using text embeddings as Queries ($Q$) and structural graph embeddings as Keys ($K$) and Values ($V$) to detect discrepancies between text quality and suspicious network activity.

### 2. Hybrid Database Architecture (RDBMS + Neo4j)
- **Primary System of Record (PostgreSQL / MySQL):** Stores structured tables for Users, Products, and Reviews, manages ACID-compliant transactions, utilizes B-tree indexing, and stores final predicted fraud scores.
- **Graph Visualization Engine (Neo4j):** Stores lightweight graph entities (`:User`), (`:Review`), and (`:Product`) synced from the RDBMS to execute Cypher topological queries, render fraud clusters, and support qualitative case studies.

---

## 1-Week Implementation Blueprint

| Phase | Timeline | Operational Tasks |
| :--- | :--- | :--- |
| **Phase 1** | Days 1–2 | Ingest YelpChi dataset into PostgreSQL/MySQL; extract 768-dim RoBERTa review embeddings offline and save to disk. |
| **Phase 2** | Days 3–4 | Build dual-branch PyTorch Geometric model (Relation-Aware GNN + `nn.MultiheadAttention` fusion layer). |
| **Phase 3** | Day 5 | Export graph structure to Neo4j; create Cypher scripts for visualization and ego-graph cluster inspection. |
| **Phase 4** | Day 6 | Train model on YelpChi; log AUC, F1-Macro, and PR-AUC metrics against baseline GCN/GAT models. |
| **Phase 5** | Day 7 | Format experimental results, generate Neo4j browser screenshots, and finalize the presentation demo. |

---

## Evaluation Framework & Key Metrics

- **Benchmark Dataset:** YelpChi dataset (containing user reviews, ratings, timestamps, and filtered ground-truth labels).
- **Performance Metrics:** Area Under ROC Curve (AUC), F1-Macro Score, and Precision-Recall Area Under Curve (PR-AUC) to evaluate detection robustness under class imbalance.
