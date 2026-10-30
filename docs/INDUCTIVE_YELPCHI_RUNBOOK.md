# Inductive YelpChi Multimodal Benchmark Runbook

For the controlled four-model comparison, use [the current benchmark method](benchmarks/README.md). This runbook preserves the identified experiment and its artifact requirements. Historical scores with different representations/protocols are not a shared ranking.

## Model Family: `raw_yelpchi_inductive_roberta_gnn_v1`

This document specifies the honest inductive replay training pipeline for NeuroGraph-DB. It provides a leak-free evaluation protocol for streaming arrival fraud detection without reusing transductive graph shortcuts.

---

## 1. Claim and Dataset Boundary

- **Source Dataset:** Pinned 47,176-row labelled `training_data.csv` from `samygithub/collective-opinion-spam-detection`.
- **Labels:** `Y` $\to$ 1 (spam), `N` $\to$ 0 (legitimate).
- **Ratings:** Parsed from `rating_OhNo` (1–5 scale).
- **Node Ordering:** Chronologically sorted by `(date, review_id)`.
- **Arrival Windows:**
  - **Train Split (60%):** Nodes 0 to 28,304 (2004-10-23 to 2011-02-06, $N=28,305$, 13.15% spam).
  - **Validation Split (20%):** Nodes 28,305 to 37,739 (2011-02-06 to 2011-11-15, $N=9,435$, 13.46% spam).
  - **Test Split (20%):** Nodes 37,740 to 47,175 (2011-11-15 to 2012-10-08, $N=9,436$, 13.26% spam).

---

## 2. Anti-Leakage & Inductive Invariants

1. **Temporal Arrival Invariant:**
   - Validation and test nodes are treated as new arrivals at time $t$.
   - Feature engineering uses only the candidate's own fields and strictly historic reviews dated earlier than the candidate.
   - Author and product cumulative counts are computed strictly in past arrival order (`cumcount()`).
   - StandardScaler is fit **exclusively** on training nodes ($N=28,305$).
2. **Relational Policy (`inductive-rur-rsr-rtr-v1`):**
   - Strictly directed from historic context to candidate node ($src < tgt$ and $date[src] \le date[tgt]$).
   - Zero future-to-past or candidate-to-historic edges.
   - Each relation is capped at the 50 most recent deterministically ordered historic neighbors.
   - **RUR:** Same reviewer ID, strictly historic to candidate (54,338 edges).
   - **RSR:** Same restaurant/product ID and rating, strictly historic to candidate (1,658,662 edges).
   - **RTR:** Same restaurant/product ID within a rolling 30-day window, strictly historic to candidate (450,271 edges).
   - Total edges: 2,163,271.
3. **Threshold Selection & Single Test Evaluation:**
   - Classification threshold is selected on validation arrivals by maximizing F1-macro.
   - The test split is evaluated **exactly once** using the frozen validation threshold.
   - Labels are omitted from the serving graph (`serving_graph.pt`).

---

## 3. Verified Run Record

- **Run ID:** `raw_yelpchi_inductive_seed42_20261025T125837Z`
- **Manifest SHA256:** `9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd`
- **Validation Threshold:** `0.787071`
- **Test Metrics:**
  - **Test ROC-AUC:** `0.8105` (0.810486)
  - **Test F1-Macro:** `0.6624` (0.662444)
  - **Test PR-AUC:** `0.4211` (0.421073)
- **Fixed Node Reproduction Score:**
  - Test Review ID: `PmQBUjV1wPZxWFWXb7S5lg` (node index 37,740)
  - Expected Score: `0.001592655316926539`
  - Reproduced Score: `0.0015926555497571826`
  - Absolute Difference: `2.33e-10` (tolerance $\le 1\times 10^{-6}$)
  - Labels Accessed: `False`

---

## 4. Local Reproduction Command

```bash
python ml/reproduce_yelpchi_inductive_bundle.py \
  --bundle-dir artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z \
  --manifest-sha256 9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd
```
