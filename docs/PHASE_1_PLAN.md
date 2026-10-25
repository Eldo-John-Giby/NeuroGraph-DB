# NeuroGraph-DB Roadmap Alignment

**Source of project direction:** the user's original proposed roadmap in the supplied attachment.  
**Current stage:** Phase 1 - repository and ML audit.  
**Updated:** 2026-10-23.

## Direction to follow

The original roadmap is the project plan. The immediate task is to turn the existing research-oriented system into a database-driven review-risk application, while retaining and verifying its ML work. Work follows these phases in order:

1. **Repository and ML audit** - inspect actual data provenance, code, checkpoints, inference support, attention outputs, and metric reproducibility. Record unsupported claims and current limitations.
2. **Database design** - prepare the ERD, data dictionary, and physical schema/migrations for review against faculty requirements. This starts after Phase 1 audit findings are established.
3. **ML inference API** - implement the Python inference path and persistence using the approved model and database contracts. First support existing dataset reviews; only add unseen-review inference after its graph insertion path is verified.
4. **Application and visualizations** - build the React application against the approved API, with role-based access and real database/model state.
5. **Verification and delivery** - Docker setup, test evidence, backup/restore proof, deployment evidence, and final report.

The nine proposed UI pages, rubric tracker, deployment choices, faculty viva questions, and AI-tool workflow are later product/delivery guidance. They are not a request to build all pages during Phase 1. The supplied lab question paper is course context; its contents do not override this roadmap. The PDF could not be text-extracted with the available local tools during this turn, so no additional rubric claims are inferred from it.

## Target stack from the roadmap

- Frontend: React + Vite + TypeScript, Tailwind CSS and shadcn/ui.
- Main API: FastAPI, using the Python ML implementation directly.
- PostgreSQL: SQLAlchemy 2.x and Alembic migrations.
- Graph: Neo4j, with durable, retryable, idempotent sync status because PostgreSQL and Neo4j do not share a transaction.
- ML: existing PyTorch/PyTorch Geometric models and Hugging Face Transformers, subject to audit validation.
- Authentication: JWT or secure sessions, Argon2id password hashing, and API/page role-based access.
- Local delivery: Docker Compose.

The current Next.js + Express + Prisma dashboard and the Streamlit research dashboard are existing repository assets, not the target architecture. Migration is part of the roadmap and must be explicit; do not continue adding product features to the Express/Prisma path as if it were the approved backend. Keep Streamlit as an optional research tool if useful.

## Phase 1: audit status and remaining evidence

### Already documented

- [MODEL_AUDIT.md](MODEL_AUDIT.md) documents the local data/model path, known synthetic artifact provenance, missing checkpoint, lack of unseen-review serving, and limits on existing metric claims.
- [IMPLEMENTATION_GAPS.md](IMPLEMENTATION_GAPS.md) records the repository-level findings and separates verified facts from unverified items.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) contains a broader engineering proposal. It is supporting material; phase ordering and target stack in this roadmap alignment document take precedence where they differ.

### Still required by Phase 1

1. Identify the authentic dataset/source, label definition, usage terms, checksum, and acquisition method, or formally scope the current demo as synthetic.
2. Locate a real compatible checkpoint and record its architecture/configuration, preprocessing version, graph/split identity, and training run. Current audit found no checkpoint.
3. If that checkpoint exists outside the scanned repository/artifact paths, load it and reproduce one fixed known review prediction. If it cannot be located, record the reproduction attempt as blocked; do not generate a substitute score.
4. Independently regenerate evaluation metrics from saved test-only predictions and link them to the exact dataset, split, checkpoint, and configuration. Mark unavailable evidence as unavailable.
5. Confirm whether the model's actual attention output is available and reproducible. Do not use illustrative weights as model explanations.
6. Record the supported inference scope. The initial product target is scoring an existing dataset review; unseen-review scoring remains unsupported until the graph-node insertion and feature path are proven.

**Phase 1 exit:** `MODEL_AUDIT.md` and an evaluation reproducibility report distinguish verified results from unsupported claims, and include a reproducible known-review result if an authentic compatible checkpoint is available. If it is not, the report must name that blocker and the team must decide whether to obtain/train a valid model before moving to live inference implementation.

## Phase 2 preview (not yet approved as a physical schema)

The original roadmap calls for a 12-table design: `users`, `roles`, `reviewers`, `products`, `reviews`, `model_versions`, `inference_runs`, `fraud_predictions`, `review_variants`, `graph_sync_jobs`, `audit_logs`, and `review_feedback`. Application login identities (`users`) remain separate from review authors (`reviewers`). This list is a design target, not a finalized ERD; Phase 2 must resolve keys, cardinalities, deletion behavior, constraints, and normalization before migrations are implemented.

The Phase 2 design should cover the roadmap's required demonstrations: CRUD, joins, aggregates, views, transactions, stored procedure, trigger/audit behavior, indexes, ORM queries, backup/restore, security, and a documented 3NF rationale. Every prediction must identify the checkpoint, preprocessing version, graph snapshot, threshold, and run. Graph sync state must be durable and retryable.

## Non-negotiable inference behavior

- Treat the output as a **risk assessment**, not a definitive fraud accusation.
- Never fabricate, hardcode, or silently substitute model scores, embeddings, graph evidence, or attention weights.
- Keep an unavailable model visibly unavailable. Historical evaluation results must be distinguishable from live inference.
- A score is not an 87% fraud probability unless calibration and validation establish that interpretation.
- Attention weights indicate model attention, not causation; pair them with observable neighborhood facts and controlled ablations.
- If Neo4j is unavailable, report graph status accurately and do not claim that a graph-based prediction completed.

## Roadmap deliverables and gates

| Phase | Deliverable | Gate before continuing |
|---|---|---|
| 1. Audit | `MODEL_AUDIT.md`, verified inference result when possible, evaluation reproducibility report | Data/checkpoint/metrics status is evidence-based; blockers are explicit |
| 2. Database design | Approved ERD, data dictionary, schema migrations, database tests | At least 8 tables and all required constraints/relationships reviewed; 3NF rationale recorded |
| 3. ML inference API | Functional FastAPI scoring and persistence | Model-backed score and provenance survive checkpoint reload and DB transaction tests |
| 4. Application | React app with RBAC and real API integration | Submission, review, history and analytics flows use live API/data with loading/error states |
| 5. Delivery | Docker, test results, backup proof, deployment and report | Clean documented run; restore is demonstrated; public demo limitations are disclosed |

## Ownership and collaboration rules from the roadmap

Respect current directory ownership (`data_pipeline/` - Avaneesh; `ml/` - Eldo; `viz/` and `docs/` - Anubhav) until the team revises it. The proposed new `backend/` and `frontend/` directories need explicit owners. Backend/API and approved database migrations can be Codex-owned; frontend implementation can be Antigravity-owned; changes to `ml/` require the ML owner; Claude can critique the architecture and viva answers. Do not have multiple agents modify the same files concurrently. Use isolated branches/worktrees and reviewable commits for shared changes.

Do not start Phase 2 schema implementation, Phase 3 inference endpoints, or Phase 4 UI migration until the applicable preceding deliverable and review gate are met. Tests are required at each phase per the roadmap, but no tests were run for this planning-only update.
