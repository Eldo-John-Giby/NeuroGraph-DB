# NeuroGraph-DB Implementation Plan

This plan follows the user's original proposed project roadmap. Phase gates are sequential: do not begin an implementation phase before its prerequisite evidence and design have been reviewed.

## Project outcome

Turn the existing research-oriented ML repository into a working, database-driven review-risk application. Preserve the research model when it is verifiable; connect submission, inference, relational persistence, graph evidence, and UI. Describe results as risk assessments, not definitive fraud findings.

## Target architecture

| Layer | Target |
|---|---|
| Frontend | React + Vite + TypeScript; Tailwind CSS + shadcn/ui |
| API | FastAPI |
| Relational data | PostgreSQL; SQLAlchemy 2.x + Alembic |
| Graph projection | Neo4j with durable sync jobs, retries, and idempotent updates |
| Inference | Existing PyTorch/PyG models and Hugging Face Transformers, after audit verification |
| Authentication | JWT or secure sessions, Argon2id, API/page RBAC |
| Local environment | Docker Compose |

The existing Next.js + Express + Prisma dashboard is a migration source, not the target stack. The Streamlit interface may remain an optional research dashboard. Stack migration must follow approved API/database contracts and preserve useful existing capabilities.

## Ordered implementation phases

### Phase 1 - Repository and ML audit

**Owners:** Codex + project team, with the ML owner validating model-specific findings.

**Work:** Inspect actual source data, preprocessing, training, checkpoint availability, known-review inference, new-review limitations, attention outputs, and evaluation artifacts. Reproduce a known prediction and regenerate metrics where valid evidence permits.

**Deliverables:** `MODEL_AUDIT.md`, a verified known-review inference result if a compatible authentic checkpoint exists, and an evaluation reproducibility report. List unsupported claims and blockers explicitly.

**Gate:** Data, checkpoint, split, and metric status are evidence-based. If the checkpoint is missing, do not simulate a prediction; record the blocker and decide whether to obtain or train a valid model before live inference work.

### Phase 2 - Database design

**Owners:** Codex + Claude architecture review + project team.

**Work:** Approve ERD, data dictionary, physical PostgreSQL schema, migration strategy, and test plan before implementation. Target 12 tables: `users`, `roles`, `reviewers`, `products`, `reviews`, `model_versions`, `inference_runs`, `fraud_predictions`, `review_variants`, `graph_sync_jobs`, `audit_logs`, and `review_feedback`. Keep application users separate from review authors.

**Required design evidence:** 3NF rationale; PK/FK/unique/check constraints; delete/update behavior; indexes; and relationship/cardinality definitions. Cover CRUD, joins, aggregates, views (`vw_high_risk_reviews`, `vw_product_risk_summary`), transactions, stored procedure, trigger/audit behavior, ORM queries, backup/restore, and security.

**Deliverables:** Approved ERD, data dictionary, schema migrations, and database tests.

**Gate:** Schema reviewed against the faculty rubric and proven to migrate onto a fresh database before the API depends on it.

### Phase 3 - ML inference API

**Owners:** Codex + ML owner.

**Work:** Build FastAPI endpoints and connect the approved relational schema to verified inference. Start by supporting inference for existing dataset reviews. Persist model version, preprocessing version, graph snapshot, threshold, run, score, attention output (if genuinely available), and analysis status. Add unseen-review inference only after validating tokenization, metadata, graph neighborhood construction, unknown/sparse reviewer behavior, and checkpoint compatibility.

**Graph behavior:** Use a durable PostgreSQL sync queue/job record for Neo4j updates. Make synchronization idempotent and retryable. If graph sync is unavailable or incomplete, expose that state and do not claim a graph-based result completed.

**Deliverable:** Functional ML inference API with tested scoring and persistence.

**Gate:** A checkpoint reload reproduces the known result; prediction persistence is transactional; inference responses carry provenance; unsupported modes fail explicitly.

### Phase 4 - Application and visualizations

**Owners:** Antigravity + Codex, after the API contract is stable.

**Work:** Build the React application with authenticated roles, review submission, saved prediction display, history/search/filter/pagination, dashboard analytics from PostgreSQL, model evaluation backed by reproducible artifacts, and Neo4j graph exploration. Include loading, empty, validation, degraded, and error states.

**Initial page priority:** Dashboard; Submit Review & Analysis; Graph Explorer; Model Evaluation; then Review History, Reviewer Management, Product Management, User Administration, and Audit/Database Operations.

**Deliverable:** Working React application with role-based access and real backend/model interaction.

**Gate:** Core user flows are checked in a browser against live local services; no fabricated counters or predictions appear.

### Phase 5 - Verification and delivery

**Current status (2026-10-24):** Partial verification recorded in [PHASE_5_VERIFICATION.md](PHASE_5_VERIFICATION.md). Automated/local checks passed, but the Phase 5 gate is not met: live PostgreSQL backup/restore, live Neo4j traversal/sync, browser-to-live-API verification, and a saved prediction from a verified model remain unverified or blocked. Do not represent Phase 5 as complete until those evidence gaps are closed or explicitly accepted by the project team.

**Owners:** All team members.

**Work:** Complete Docker setup, relevant automated tests, backup and restore demonstration, deployment, and final report. Verify local clean startup, relational operations, actual Neo4j traversal, saved prediction with model identity, and documented demo limitations.

**Deliverable:** Docker setup, test results, backup proof, deployment evidence, and final report.

**Gate:** A clean documented run can be demonstrated; restored data and service behavior are checked; cloud limits and model artifact handling are explicit.

## Engineering rules

- Never hardcode or fabricate predictions, model outputs, database counters, or query latency claims.
- Never change model architecture or dataset without recording the reason and affected results.
- Keep historical evaluation separate from live inference.
- Do not interpret a score as a calibrated fraud probability without calibration evidence.
- Attention is not causal explanation; report actual graph facts and avoid causal claims.
- Keep secrets out of source control; use environment configuration and safe examples.
- Respect current folder ownership until explicitly revised, establish owners for new `backend/` and `frontend/` roots, and avoid concurrent edits to shared files.
- Use small reviewable changes and run phase-appropriate checks before reporting a phase complete.

## Relationship to other planning documents

[PHASE_1_PLAN.md](PHASE_1_PLAN.md) records the current phase status, repository evidence, and immediate Phase 1 remaining work. [MODEL_AUDIT.md](MODEL_AUDIT.md) and [IMPLEMENTATION_GAPS.md](IMPLEMENTATION_GAPS.md) contain the current findings. These files do not authorize skipping the roadmap's phase gates.
