# NeuroGraph-DB Model Card

## Model Details

- **Model Families:**
  - `yelpchi_structured_feature_gnn_baseline` (Structured MAT baseline)
  - `raw_yelpchi_multimodal_roberta_pyg_gnn` (Transductive multimodal benchmark)
  - `raw_yelpchi_inductive_roberta_gnn_v1` (Inductive temporal replay model)
- **Primary Architecture:** Dual-Branch Relation-Aware Graph Transformer & PyG GraphSAGE with Cross-Attention Fusion
- **Language Model Backbone:** `FacebookAI/roberta-base` (768-dimensional embeddings, frozen weights)
- **Tokenizer Revision:** Hugging Face commit `e2da8e2f811d1448a5b465c236feacd80ffbac7b`
- **Graph Framework:** PyTorch Geometric (PyG 2.3+) with relation-specific `SAGEConv`
- **Output:** Calibrated fraud risk score $\in [0, 1]$, binary decision (`flagged` vs. `cleared`), and per-relation attention weights (`w_rur`, `w_rsr`, `w_rtr`)

---

## Intended Use & Scope

### Primary Intended Use
NeuroGraph-DB is intended for fraud analysts, trust & safety teams, and platform operators to triage, prioritize, and investigate suspicious online review behavior. The system identifies coordinated review-bombing campaigns, collusive reviewer clusters, and camouflaged spam reviews that blend benign-looking ratings across target products.

### Critical Risk-Score Limitation
> [!IMPORTANT]
> **A predicted risk score prioritizes investigation; it is not proof of fraud.**
> A high fraud score indicates that the combination of text semantics and relational graph neighborhood exhibits statistical characteristics common to filtered reviews in the benchmark dataset. Automated punitive actions (e.g., account termination or legal notices) should never be taken solely on model scores without human analyst review and corroborating business evidence.

### Out-of-Scope Use Cases
- Automated defamation or legal liability determinations.
- Evaluation of reviews in languages other than English without fine-tuning.
- Real-time zero-shot scoring of platforms with entirely distinct relation topologies (e.g., social networks without product entities).

---

## Dataset Provenance & Benchmark Boundaries

NeuroGraph-DB recognizes two distinct, non-interchangeable benchmark dataset formulations:

### 1. Anonymous 45,954-Node MAT Benchmark (`YelpChi.mat`)
- **Origin:** Classical DGFraud / academic `.mat` benchmark file.
- **Properties:** 45,954 nodes, 32 handcrafted numeric metadata features, 3 adjacency matrices (RUR, RTR, RSR), binary labels (`39,277` legitimate, `6,677` spam).
- **Limitation:** Contains **no raw review text**. Semantic embeddings cannot be generated from this file.

### 2. Labelled Raw 47,176-Review YelpChi Benchmark (`training_data.csv`)
- **Origin:** Pinned dataset `samygithub/collective-opinion-spam-detection`.
- **Properties:** 47,176 fully labelled raw English reviews with review IDs, author IDs, restaurant product IDs, star ratings (`rating_OhNo`), timestamps, and labels (`Y` $\to$ spam: 1, `N` $\to$ legitimate: 0).
- **Alignment:** Nodes are chronologically sorted by `(date, review_id)`, binding the RoBERTa text embeddings to the graph adjacency topology bit-for-bit.

> [!WARNING]
> Because no audited, one-to-one cross-walk exists between the 45,954-node MAT file and the 47,176 raw review CSV, **they cannot be merged**. They represent separate benchmarks and must never be presented as direct ablations of each other.

---

## Benchmark Performance & Protocol Distinction

The following table reports the verified test set metrics across the three evaluation protocols.

> [!IMPORTANT]
> **These results reflect fundamentally distinct protocols, feature sets, and graph topologies. They are not direct architectural ablations.**
> - The **Structured MAT GNN** operates on anonymous 32-dimensional metadata with full graph visibility.
> - The **Raw Multimodal Model** evaluates transductive RoBERTa + graph fusion on the 47,176-node text corpus.
> - The **Inductive Multimodal Model** strictly enforces chronological arrival replay with zero future edge leakage and train-only feature scalers.

| Model | Protocol | ROC-AUC | F1-Macro | PR-AUC | Threshold |
|---|---:|---:|---:|---:|---:|
| Structured MAT GNN | Transductive known-node | 0.9331 | 0.8078 | 0.7454 | 0.7673 |
| Raw multimodal model | Transductive known-node | 0.8439 | 0.6860 | 0.4507 | 0.6732 |
| Inductive multimodal model | Temporal arrival replay | 0.8105 | 0.6624 | 0.4211 | 0.7871 |

### Protocol Definitions

1. **Structured MAT GNN (`yelpchi_structured_feature_gnn_baseline`):**
   - Transductive evaluation on the legacy 45,954-node `.mat` graph.
   - Run ID: `yelpchi_gnn_seed42_20261024T234034Z`.
   - Threshold derived from validation split ($0.7673$).
2. **Raw Multimodal Model (`raw_yelpchi_multimodal_roberta_pyg_gnn`):**
   - Transductive known-node evaluation on the 47,176-node raw text graph.
   - Run ID: `raw_yelpchi_multimodal_seed42_20261025T071547Z`.
   - Manifest SHA-256: `653729f3fdd63f23ce82849b37dfa76a4dd08242bb5c05761a44ca799692defb`.
   - Fixed review `--AweNX8vPGD` reproduces score `0.00680473` within $1\times 10^{-6}$.
3. **Inductive Multimodal Model (`raw_yelpchi_inductive_roberta_gnn_v1`):**
   - Honest temporal replay protocol simulating real-time streaming arrivals.
   - Run ID: `raw_yelpchi_inductive_seed42_20261025T125837Z`.
   - Manifest SHA-256: `9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd`.
   - Fixed review `PmQBUjV1wPZxWFWXb7S5lg` reproduces score `0.00159266` within $2.33\times 10^{-10}$.

---

## Model Architecture Details

The proposed multimodal architecture integrates semantic and relational information through four stages:

1. **Semantic Feature Extraction:**
   - Review text is tokenized using `FacebookAI/roberta-base` (max token length 192).
   - Wordpiece representations are mean-pooled across attention-masked tokens into a 768-dimensional dense vector $h_{\text{text}}$.
   - Weights remain strictly frozen during GNN training to prevent catastrophic forgetting and overfitting.
2. **Behavioral Metadata Projection:**
   - 14 label-free engineered features (author activity rate, product rating deviation, temporal interval, character/word lengths, sentiment cyclics).
   - Normalized using `StandardScaler` fitted strictly on training arrival data.
3. **Relation-Specific Message Passing:**
   - Three independent PyG `SAGEConv` layers process heterogeneous neighborhood subgraphs:
     - **RUR:** Review–User–Review (author sharing)
     - **RSR:** Review–Same Rating–Review (product & rating sharing)
     - **RTR:** Review–Temporal–Review (product & rolling 30-day temporal proximity)
4. **Relation Attention & Gated Fusion:**
   - A learned projection maps $h_{\text{text}}$ into relation query space, computing softmax attention weights $[w_{\text{rur}}, w_{\text{rsr}}, w_{\text{rtr}}]$ across structural embeddings.
   - The aggregated structural representation is combined with $h_{\text{text}}$ through a learned gating mechanism before final linear classification.

---

## Checksum & Manifest Verification Model

To ensure scientific integrity and eliminate silent model substitution:

- **Immutable Run Manifests:** Every model bundle contains a cryptographic `run_manifest.json` detailing bundle type, model config, dataset SHA-256, constituent file hashes, environment specifications, and validation-derived decision thresholds.
- **Fail-Closed Runtime Checks:**
  1. The manifest's SHA-256 must match the committed run record in Git.
  2. All internal files (`model_state.pt`, `serving_graph.pt`, `preprocessing.json`, etc.) are hashed and compared to manifest values.
  3. The local fixed-node reproduction check executes forward inference and asserts numerical parity within tolerance $\le 10^{-6}$.
  4. If any check fails, the serving layer immediately aborts (HTTP 503 `bundle_verification_failed`) and writes zero fabricated outputs.

---

## Known Limitations & Operational Considerations

1. **Domain & Geographic Transferability:**
   - The YelpChi benchmark represents Chicago-area restaurant and hotel reviews collected between 2004 and 2012. Vocabulary, rating conventions, and user behavior may not transfer directly to other platforms (e.g., Amazon product reviews, app store ratings) without domain fine-tuning.
2. **Score Calibration:**
   - Output scores are optimized for discriminative ranking (ROC-AUC / PR-AUC) under severe class imbalance (~13.2% spam). Scores reflect relative anomaly risk rather than exact Bayesian probabilities. Decision thresholds must be calibrated to organizational false-positive tolerance.
3. **Heuristic Ground-Truth Labels:**
   - Ground-truth labels reflect Yelp's automated filtering algorithm, not absolute manual verification. Systematic omissions or false positives present in the legacy filter are inherited by the training data.
4. **Adversarial Concept Drift:**
   - LLM-generated review camouflage evolves rapidly. Periodic retraining using newly curated arrival batches is required to maintain robustness against novel linguistic camouflage styles.
5. **Cold-Start Reviewers & Products:**
   - Reviews from first-time reviewers on new products have zero historic RUR, RSR, or RTR edges. In these isolated cases, the model relies primarily on the semantic text branch and behavioral metadata until structural edges accumulate.
