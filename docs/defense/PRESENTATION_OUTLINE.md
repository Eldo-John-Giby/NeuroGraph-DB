# NeuroGraph-DB Defense Presentation Outline (12 Slides)

This document outlines the presentation slide deck for the NeuroGraph-DB academic defense.

---

### Slide 1: Problem Definition & Threat Model
- **Title:** The Camouflage Review Spam Challenge
- **Core Problem:** Online platforms face sophisticated, LLM-generated fake review rings that evade traditional detection.
- **Fraud Camouflage:** Fraudulent actors post benign-looking ratings across random products to manipulate graph topology, dilute heterophily signals, and bypass standard GNNs.
- **Thesis Statement:** Effective defense requires combining frozen deep linguistic representations with multi-relational graph topology, supported by hybrid database infrastructure and honest temporal evaluation protocols.

---

### Slide 2: Target Audience & Operational Personas
- **Title:** Operational Personas & Workflows
- **Restaurant & Business Owners:** Require non-technical, explainable fraud assessments with transparent relation-attention breakdowns to understand why a review was flagged.
- **Trust & Safety Analysts:** Need multi-hop graph exploration in Neo4j, collusive ring identification, and immutable cryptographic evidence tracking.
- **System Administrators:** Enforce role-based access control, manage historical graph context permissions, and supervise fail-closed model integrity.

---

### Slide 3: End-to-End System Architecture
- **Title:** Hybrid Database & Inference Architecture
- **Presentation Flow:** High-level architectural diagram illustrating presentation, API, storage, and worker layers.
- **Hybrid Storage Rationale:**
  - PostgreSQL 15: ACID system of record, 3NF relational normalization, B-tree indexes, and transactional audit trails.
  - Neo4j 5: Read-optimized index-free adjacency graph projection for sub-5ms Cypher pattern matching.
- **Asynchronous Execution:** Durable leased worker queue (`inductive_inference_jobs`) decoupling HTTP ingestion from GPU inference.

---

### Slide 4: Relational Schema & Integrity Constraints
- **Title:** Relational Modeling & Database Constraints
- **Schema Design:** 3NF normalization covering `users`, `products`, `reviews`, `inference_runs`, `fraud_predictions`, and `inductive_prediction_evidence`.
- **Database-Level Invariants:**
  - `ck_model_provenance` & `ck_graph_snapshot_provenance`: Strict isolation between real and synthetic demo records.
  - `ck_snapshot_context_scope`: Ensures batch context is permitted only on valid, scoped snapshots.
  - Foreign-key cascade rules and non-null constraints ensuring relational consistency.

---

### Slide 5: Graph Schema & Topological Traversals
- **Title:** Graph Design & Collusive Ring Discovery
- **Graph Schema:** Heterogeneous structure featuring `(:User)`, `(:Review)`, and `(:Product)` nodes with `[:WROTE]` and `[:ABOUT]` edges.
- **Relational Projections:** Derived multi-relational edges (RUR: same author, RSR: same restaurant & rating, RTR: same restaurant within 30 days).
- **Cypher Traversal Advantage:** Multi-hop collusive review ring detection executes in $<7\text{ ms}$ on Neo4j compared to $>320\text{ ms}$ for equivalent nested SQL self-joins.

---

### Slide 6: The Three-Lane Provenance Model
- **Title:** Strict Three-Lane Provenance Separation
- **Lane 1 (Synthetic Restaurant Scenario):** Harbor Table review-bombing demo; labeled `synthetic_demo`; **strictly zero ML scoring**.
- **Lane 2 (Verified Transductive Benchmark):** Frozen 47,176-review raw YelpChi benchmark; transductive known-node baseline; ROC-AUC `0.8439`.
- **Lane 3 (Inductive Restaurant CSV Assessment):** Live CSV batch scoring against permitted historic snapshots; temporal streaming replay; ROC-AUC `0.8105`.
- **Ethical & Scientific Value:** Eliminates conflation between research benchmarks and synthetic UI demonstrations.

---

### Slide 7: Multimodal ML Architecture
- **Title:** Dual-Branch Cross-Attention Architecture
- **Semantic Branch:** Frozen `FacebookAI/roberta-base` generating 768-d masked-mean embeddings.
- **Structural Branch:** Independent PyG `SAGEConv` layers processing RUR, RSR, and RTR relation subgraphs.
- **Cross-Attention & Gated Fusion:** Text-conditioned attention dynamically weights structural vectors ($w_{\text{rur}} + w_{\text{rsr}} + w_{\text{rtr}} = 1.0$), combined with text representations via a learned gate before classification.

---

### Slide 8: Evaluation Protocol & Anti-Leakage Invariants
- **Title:** Honest Inductive Arrival Replay
- **Temporal Partitioning:** Chronologically ordered Train (60%), Validation (20%), and Test (20%) windows.
- **Anti-Leakage Guarantees:**
  - Strictly past-to-present edge directionality ($src < tgt$ and $date[src] \le date[tgt]$).
  - Train-only feature scaler fitting.
  - Validation-only threshold selection ($0.787071$).
  - Label-free SQL context queries.
  - Deterministic 50-neighbor caps with tie-breaking.

---

### Slide 9: Benchmark Performance & Metrics
- **Title:** Verified Empirical Results
- **Presentation of Metrics Table:**
  | Model | Protocol | ROC-AUC | F1-Macro | PR-AUC | Threshold |
  |---|---:|---:|---:|---:|---:|
  | Structured MAT GNN | Transductive known-node | 0.9331 | 0.8078 | 0.7454 | 0.7673 |
  | Raw multimodal model | Transductive known-node | 0.8439 | 0.6860 | 0.4507 | 0.6732 |
  | Inductive multimodal model | Temporal arrival replay | 0.8105 | 0.6624 | 0.4211 | 0.7871 |
- **Key Insight:** Explain that the transductive-to-inductive delta reflects honest real-world evaluation where future graph shortcuts are prohibited.

---

### Slide 10: Live Demonstration Overview
- **Title:** System Walkthrough Route (7 Minutes)
- **Demo Sequence:**
  1. Authentication & RBAC.
  2. Three-lane dashboard navigation.
  3. Synthetic Neo4j campaign analysis.
  4. Transductive benchmark inspection.
  5. Fail-closed model registry and fixed-node verification.
  6. Inductive CSV upload and transactional intake.
  7. Background worker execution.
  8. Relation-attention explanation and cryptographic evidence modal.
  9. PostgreSQL audit log verification.

---

### Slide 11: System Integrity & Cryptographic Provenance
- **Title:** Reproducibility & Cryptographic Integrity
- **Manifest Verification:** Pinned SHA-256 hashes for `run_manifest.json`, tokenizer revision, and constituent model files.
- **Fixed-Node Guarantees:** Local forward reproduction asserts score parity within numerical tolerance ($\le 10^{-6}$).
- **Persisted Evidence:** Every prediction permanently stores stitched graph SHA-256, feature hashes, embedding hashes, and connected neighbor IDs.
- **Zero Fabrication:** Fail-closed design ensures missing dependencies result in explicit error states rather than synthetic outputs.

---

### Slide 12: Limitations & Future Directions
- **Title:** Limitations & Future Research
- **Current Limitations:** Chicago restaurant domain specificity, uncalibrated probability scores under extreme imbalance, and legacy heuristic ground truth.
- **Future Work:**
  - Domain adaptation for general e-commerce platforms.
  - Platt scaling / isotonic regression for calibrated Bayesian posterior risks.
  - Self-supervised graph contrastive pretraining.
  - Streaming continual learning to counter evolving LLM camouflage.
