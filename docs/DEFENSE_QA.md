# NeuroGraph-DB Academic Defense Q&A

This document provides concise, authoritative answers to core architectural, machine learning, and database design questions for the defense committee.

---

### 1. Why are both PostgreSQL and Neo4j used in the same architecture?
**Answer:**
We employ a **hybrid storage architecture** tailored to workload specialization:
- **PostgreSQL 15 (System of Record):** Provides ACID guarantees, 3NF normalization, strict relational integrity (foreign keys, check constraints), audit logging, and sub-millisecond point lookups via B-tree indexes ($0.4\text{ ms}$).
- **Neo4j 5 (Graph Traversal Engine):** Provides index-free adjacency for complex topological traversals. Identifying a 3-hop collusive review ring requires expensive nested-loop self-joins in relational SQL ($>320\text{ ms}$), whereas Cypher graph pattern matching executes in $<7\text{ ms}$.
- PostgreSQL acts as the single source of truth; Neo4j is an asynchronous, read-optimized projection.

---

### 2. Why is synthetic demo data shown alongside real benchmarks?
**Answer:**
To maintain strict **scientific provenance separation**:
- Lane 1 uses synthetic review-bombing campaigns (Harbor Table) strictly to demonstrate UI workflows, B-tree query plans, and Neo4j Cypher traversals without deceptive claims.
- Real ML models are explicitly quarantined: synthetic data is tagged `provenance = 'synthetic_demo'` and barred from interacting with real neural networks.
- This prevents the common academic pitfall of showcasing unverified model outputs on mock data.

---

### 3. What is the fundamental difference between transductive and inductive evaluation?
**Answer:**
- **Transductive Evaluation (Lane 2):** Assumes a closed-world graph. All 47,176 nodes and multi-relational edges are fixed and visible during GNN message passing; only labels are masked during training.
- **Inductive Temporal Evaluation (Lane 3):** Simulates real-time streaming arrivals. Candidate reviews arrive at time $t$ and can only aggregate information from reviews dated prior to $t$. Future edges and future reviews do not exist.

---

### 4. How does the inductive protocol prevent temporal data leakage?
**Answer:**
Through five strict anti-leakage invariants:
1. **Directional Causality:** Edges are strictly directed from past reviews to candidate reviews ($src < tgt$ and $date[src] \le date[tgt]$).
2. **Train-Only Scalers:** `StandardScaler` is fitted exclusively on the 60% training window ($N=28,305$); validation and test arrivals are transformed using frozen training statistics.
3. **Validation-Only Threshold:** The decision threshold ($0.787071$) is calibrated strictly on validation arrivals; the test split is evaluated exactly once.
4. **Label-Free Context Queries:** SQL queries for historical context project only relational metadata and explicitly omit `ground_truth_label` and `label_source`.
5. **Snapshot Immutability:** Historical graph snapshots are read-only; candidate graph stitching occurs transiently in worker memory.

---

### 5. Why are inductive test metrics (ROC-AUC 0.8105) lower than transductive metrics (ROC-AUC 0.8439)?
**Answer:**
The metric reduction is **expected, mathematically honest, and realistic**:
- In transductive setups, message passing exploits bidirectional edges and future neighborhood context.
- In honest streaming evaluation, future edges are prohibited, cumulative user/product statistics are unobserved, and early review arrivals suffer from sparse historical context.
- The 0.8105 ROC-AUC reflects true generalization to unseen temporal arrivals rather than inflated transductive graph shortcuts.

---

### 6. How does the system verify model bundles and prevent silent model substitution?
**Answer:**
Via a multi-stage **fail-closed verification routine**:
1. Computes the SHA-256 of `run_manifest.json` and verifies exact parity with the committed run record in Git.
2. Hashes every internal file (`model_state.pt`, `serving_graph.pt`, `preprocessing.json`, etc.) against manifest checksums.
3. Asserts the Hugging Face tokenizer matches the pinned commit `e2da8e2f811d1448a5b465c236feacd80ffbac7b`.
4. Executes forward inference on a designated fixed review and asserts numerical score parity within tolerance $\le 10^{-6}$.
5. If any check fails, the runtime aborts immediately (HTTP 503) and writes zero fake predictions.

---

### 7. Why does a predicted risk score not constitute proof of fraud?
**Answer:**
- Fraud risk scores are statistical probability estimates produced by combining RoBERTa text semantics with PyG relational neighborhood embeddings.
- They reflect similarity to historically filtered spam patterns in YelpChi, not legal culpability.
- Our model card and UI explicitly specify that scores are intended for **human analyst triage and audit prioritization**, never for automated punitive action.

---

### 8. How are RBAC, audit logging, idempotency, and database constraints enforced?
**Answer:**
- **RBAC:** FastAPI route dependencies (`require_roles("ADMIN")`) restrict administrative endpoints (user creation, snapshot permission, graph sync) while allowing researchers access to intake and personal batch scoring.
- **Audit Logs:** The `audit_logs` table records every operational state transition with actor ID, entity key, and before/after JSON diffs.
- **Idempotency:** Client requests supply an `Idempotency-Key` header; duplicate submissions return the existing `BatchAnalysis` without duplicating inference runs.
- **Database Constraints:** PostgreSQL enforces `ck_model_provenance`, `ck_graph_snapshot_provenance`, `ck_snapshot_context_scope`, and foreign-key integrity at the storage engine level.

---

### 9. Why are uploaded CSV rows persisted in PostgreSQL before model scoring?
**Answer:**
- **Decoupled Architecture:** Separates fast HTTP intake validation from compute-intensive neural network inference.
- **Auditability:** Preserves raw uploaded records, row numbers, and validation errors in `batch_analysis_rows` regardless of downstream ML worker status.
- **Fault-Tolerant Asynchronous Execution:** Allows background workers to lease jobs via `inductive_inference_jobs`, handle retries, and recover cleanly from worker restarts without dropping uploaded batches.

---

### 10. What limitations exist and what remains future work?
**Answer:**
- **Domain Generalization:** Current models are trained on Chicago restaurant/hotel reviews; cross-domain adaptation to e-commerce (e.g., Amazon) requires domain fine-tuning.
- **Score Calibration:** Raw sigmoid outputs optimize discriminative rank (ROC-AUC / PR-AUC); future work will integrate Platt scaling or isotonic regression for calibrated Bayesian posterior risks.
- **Continuous Adaptation:** Real-world spam rings adapt dynamically; future work will incorporate streaming continual learning and graph contrastive self-supervised pretraining.
