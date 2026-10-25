# NeuroGraph-DB FastAPI backend

Phase 3 backend implementation target: PostgreSQL, SQLAlchemy 2.x, Alembic, FastAPI, Argon2id password hashes, short-lived signed access tokens, and hashed rotating refresh credentials in `session_tokens`.

## Local setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env
# Set DATABASE_URL and a random JWT_SECRET_KEY of at least 32 characters.
alembic upgrade head
BOOTSTRAP_ADMIN_EMAIL=admin@example.edu BOOTSTRAP_ADMIN_PASSWORD='use-a-long-unique-password' python scripts/seed_roles.py
uvicorn app.main:app --reload
```

`GET /health/live` checks only that the API process responds. `GET /health/ready` also checks PostgreSQL and queries for verified-real model/preprocessing registrations; a registration does not make the service ready because no scoring runtime is loaded. A configured Neo4j URI is reported as `configured_unverified` until a real connection check and sync worker exist. `POST /api/v1/graph-sync-jobs` persists review or snapshot jobs; no worker is included, so jobs remain queued and the status endpoint reports that truthfully.

Refresh cookies are `Secure`, `HttpOnly`, and `SameSite=Strict` by default. For local HTTP-only development, explicitly set `COOKIE_SECURE=false`; use HTTPS anywhere credentials leave a developer machine.

## Inference state

Inference fails closed before creating a run or prediction. Status and eligibility read model provenance, lifecycle, checkpoint fields, and preprocessing lifecycle from PostgreSQL. Only `real` provenance is eligible for real inference. `synthetic_demo` models cannot be verified and are not served by the real inference endpoint. A DB-verified real model would still return `503 model_runtime_unavailable` until a compatible runtime is loaded. `artifacts/models/neurograph_best.pt` remains unverified: there is no matching training manifest or checkpoint-linked threshold/preprocessing version, and a direct forward pass does not reproduce the saved predictions (closest saved NeuroGraph clean/clean run has mean absolute score difference about `0.2603`). The available graph has been audited as synthetic. The backend does not convert a candidate file or historical parquet into a response.

The implemented interface accepts only known review IDs and the design restricts registered inference mode to `known_node_only`; no unseen-review path is provided. A model runtime adapter and registration workflow must remain disabled until an owner supplies a verifiable checkpoint/config/preprocessing/graph/run bundle.

## CSV batch intake

`POST /api/v1/batch-analyses` accepts the six-column review CSV described in [BATCH_ANALYSIS.md](../docs/BATCH_ANALYSIS.md). Accepted rows and per-row validation outcomes are persisted transactionally; reviewer/product external keys are resolved inside the submitted `source_system`. Use the batch status and paginated results endpoints to inspect partial validation. An ADMIN must explicitly permit an available graph snapshot before it can be selected as historical context. Batch scoring is currently blocked: no batch creates an `inference_runs` row or score unless a real verified model/preprocessing/graph tuple and compatible loaded runtime exist. Provider protocols are defined for RoBERTa embeddings and manifest-ordered behavioral features; `backend/app/services/batch_graph.py` has a label-free in-memory RUR/RSR/RTR edge builder. No scoring providers or Neo4j batch writer are active.

## Tests and migrations

```bash
cd backend
python -m pytest -q
alembic heads
```

The tests use SQLite in memory for API/auth/integrity behavior. They do not replace PostgreSQL migration, transaction, or concurrency verification. Use PostgreSQL before treating database behavior as production-ready.

## Synthetic UI demo seed

After applying Alembic migrations, an explicitly opted-in local demo can be seeded with:

```bash
cd backend
DEMO_MODE=true python scripts/seed_demo_batch.py
```

The script creates 50 `reviewers` (review authors, not app-login `users`), 10 products, 200 synthetic reviews, and one `synthetic_demo` model/run with generated scores and demo attention weights. The model remains `registered` and has no checkpoint; the run's synthetic provenance and attention payload identify the values as generated display data. No Neo4j graph is written. Do not describe these values as model predictions or performance evidence. The script refuses to run unless `DEMO_MODE=true`.
