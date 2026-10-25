# NeuroGraph-DB Release Checklist (v1.0-defense)

This checklist tracks the deployment, artifact integrity, verification benchmarks, and live defense demonstration readiness for NeuroGraph-DB.

---

## 1. Release Identification & Version Control

- [ ] **Git Commit SHA & Release Tag**
  - Defense Base Commit: `b4039b5f9c98830d0e1e999b1434062c71221aae`
  - Release Branch: `release/v1.0-defense`
  - Release Tag: `v1.0-defense`
- [ ] **Clean Working Tree & Isolation**
  - `git status --short` confirms zero uncommitted modifications or untracked debris.
- [ ] **Repository Hygiene**
  - No secret keys, credentials, raw CSV datasets, `.pt` embedding tensors, or `.pt` weight files committed.
  - Verified `.gitignore` blocks `.env`, `artifacts/`, `data_pipeline/raw/`, `ml/models/checkpoints/`, and `.kaggle/`.

---

## 2. Database Migrations & Schemas

- [ ] **Alembic Migration Head**
  - Migration Head ID: `0005_inductive_batch_scoring` (`0005_inductive_batch_scoring.py`)
  - Target Tables Verified:
    - `graph_snapshots.context_scope_key`
    - `model_versions.supported_inference_mode` (`known_node_only`, `inductive_batch_v1`)
    - `inductive_inference_jobs` (durable worker queue with lease management)
    - `inductive_prediction_evidence` (cryptographic provenance and neighbor counts)
  - Execution Check:
    ```bash
    cd backend && alembic upgrade head
    ```
- [ ] **Historical Row Preservation**
  - Schema migrations verified non-destructive on existing historical records via `tests/test_migration_inductive_batch.py`.

---

## 3. Automated Test Suites & Build Verification

- [ ] **Backend Test Suite (64 / 64 Passed)**
  - Command:
    ```bash
    cd backend && pytest -v
    ```
  - Result: `64 passed, 76 warnings in 16.17s`
  - Test Modules Verified:
    - `test_api.py` (Authentication, sessions, RBAC, users, reviews, models)
    - `test_batch_graph.py` (Graph construction, projection checks)
    - `test_inductive_csv_scoring.py` (17 tests: schema validation, anti-leakage, evidence, idempotency)
    - `test_inductive_replay.py` (Temporal split windows, chronological feature bounds)
    - `test_migration_inductive_batch.py` (Alembic schema migration and constraint checks)
    - `test_synthetic_campaigns.py` (Attack campaign aggregation, product summaries)
    - `test_verified_multimodal.py` (Transductive bundle verification and reproduction)
- [ ] **Frontend Build (Zero Errors)**
  - Command:
    ```bash
    cd db-dashboard/frontend && npm run build
    ```
  - Result: Next.js 14.2 compiled successfully with 0 type errors across all 14 routes.

---

## 4. Environment & Service Health Checks

- [ ] **Docker Containers Active**
  - PostgreSQL container running: `docker compose -f data_pipeline/docker-compose.postgres.yml up -d` (Port 5432)
  - Neo4j container running: `docker compose -f viz/docker-compose.neo4j.yml up -d` (Ports 7474, 7687)
- [ ] **FastAPI Backend Operational**
  - Server running on `http://localhost:8000`
- [ ] **System Readiness Verification**
  - Endpoint `GET /health/ready` returns HTTP 200:
    - `postgresql`: `ready`
    - `verified_model`: `ready`
    - `neo4j`: `ready` (or `configured_unverified`)

---

## 5. ML Benchmark Bundles & Fixed-Node Cryptographic Reproductions

- [ ] **Lane 2: Verified Transductive Benchmark Bundle**
  - Bundle Type: `raw_yelpchi_multimodal_roberta_pyg_gnn`
  - Model Claim: Raw YelpChi review graph; frozen RoBERTa embeddings with RUR/RSR/RTR PyG GraphSAGE fusion
  - Bundle Directory: `artifacts/verified_multimodal/raw_yelpchi_multimodal_seed42_20261025T071547Z`
  - Manifest SHA-256:
    `653729f3fdd63f23ce82849b37dfa76a4dd08242bb5c05761a44ca799692defb`
  - Test Performance:
    - ROC-AUC: `0.8439` (0.843882)
    - F1-Macro: `0.6860` (0.685993)
    - PR-AUC: `0.4507` (0.450667)
    - Validation Threshold: `0.673232`
  - Fixed-Node Reproduction Check:
    - Review ID: `--AweNX8vPGD` (Node Index 2)
    - Expected Score: `0.006804733537137508`
    - Reproduction Command:
      ```bash
      python ml/reproduce_yelpchi_multimodal_bundle.py \
        --bundle-dir artifacts/verified_multimodal/raw_yelpchi_multimodal_seed42_20261025T071547Z \
        --manifest-sha256 653729f3fdd63f23ce82849b37dfa76a4dd08242bb5c05761a44ca799692defb
      ```
    - Status: **PASSED** (labels accessed: `false`)

- [ ] **Lane 3: Verified Inductive Replay Benchmark Bundle**
  - Bundle Type: `raw_yelpchi_inductive_roberta_gnn_v1`
  - Model Family: `raw_yelpchi_inductive_roberta_gnn_v1`
  - Relation Policy: `inductive-rur-rsr-rtr-v1`
  - Bundle Directory: `artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z`
  - Manifest SHA-256:
    `9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd`
  - Test Performance:
    - Test ROC-AUC: `0.8105` (0.810486)
    - Test F1-Macro: `0.6624` (0.662444)
    - Test PR-AUC: `0.4211` (0.421073)
    - Validation Threshold: `0.787071`
  - Fixed-Node Reproduction Check:
    - Review ID: `PmQBUjV1wPZxWFWXb7S5lg` (Node Index 37,740)
    - Expected Score: `0.001592655316926539`
    - Reproduced Score: `0.0015926555497571826` (Difference: `2.33e-10` $\le 10^{-6}$)
    - Reproduction Command:
      ```bash
      python ml/reproduce_yelpchi_inductive_bundle.py \
        --bundle-dir artifacts/verified_inductive/raw_yelpchi_inductive_seed42_20261025T125837Z \
        --manifest-sha256 9d4f10a81937987ae7588d86e29191d355af296c6efc29ec3e5b331282d23edd
      ```
    - Status: **PASSED** (labels accessed: `false`)

---

## 6. Live Defense Demonstration Artifacts

- [ ] **Prepared Demo Upload CSV**
  - CSV file formatted with headers:
    `review_id,reviewer_id,product_id,rating,review_date,review_text`
  - Zero label columns included (`Label` or `ground_truth_label` omitted).
  - Contains candidate reviews simulating new arrivals against permitted historic context snapshot.
- [ ] **Backup Demo Recording & Logs**
  - Offline video recording or timestamped screen walkthrough demonstrating:
    1. Lane 1 synthetic campaign review exploration.
    2. Lane 2 verified benchmark statistics and fixed-node explanation.
    3. Lane 3 CSV upload, queued worker lease processing, relation attention breakdown, and cryptographic evidence modal inspection.
- [ ] **Defense Runbook & Presentation Deck Alignment**
  - Presentation slides and demo sequence cross-referenced to `docs/ARCHITECTURE.md` and `docs/INDUCTIVE_YELPCHI_RUNBOOK.md`.
