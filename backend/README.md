# FastAPI backend

The deployed API uses Python 3.11, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Neo4j 5 and verified CPU model runtimes. The authoritative schema has 23 domain tables through migration `0007_database_features`.

## Run locally

Follow the [root installation guide](../README.md). From the repository root, install `./backend[test,deploy]` in a virtual environment. Configure an ignored `backend/.env` using `.env.example`, then:

```sh
cd backend
alembic upgrade head
python scripts/seed_roles.py
# Provide ADMIN_PASSWORD and RESEARCHER_PASSWORD privately.
python scripts/seed_users.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use `COOKIE_SECURE=false` only for HTTP localhost. Production cookies remain Secure/HttpOnly. Database credentials, signing secrets and cloud tokens do not belong in frontend configuration.

## Implemented workflows

- Authentication, rotating refresh sessions, logout and role checks.
- Validated CSV intake, canonical identities, source-scoped duplicate handling and per-user receipts.
- Verified inductive scoring of new CSV rows, durable job/run records and saved evidence.
- Private history and results; explicit admin access to all-user history.
- Neo4j projection of the relationships used by a saved analysis.
- Review feedback CRUD and administrator moderation using a PostgreSQL procedure.
- Aggregate views and transactional redacted feedback audit trigger.
- Separate known-node reference runtimes and clearly labelled synthetic examples.

The processing endpoint calls the worker function synchronously while preserving durable job state. An autonomous background worker and automatic model retraining are not claimed.

## Model artifacts

The current model family is `raw_yelpchi_inductive_roberta_gnn_v1`; registration and exact bundle requirements are documented in the [inductive runbook](../docs/INDUCTIVE_YELPCHI_RUNBOOK.md). Missing/mismatched bundles fail closed. Historical model records are not substitutes for checkpoints, encoder files or serving graphs.

The [controlled comparison](../docs/benchmarks/README.md) is a recorded scientific report rendered by the frontend. It reuses the deployed seed-42 checkpoint without changing stored production predictions.

## Checks

```sh
cd backend
PYTHONPATH=..:. pytest
alembic heads
```

Private-bundle integration tests skip when their exact bundles are absent. PostgreSQL-specific tests require `TEST_POSTGRES_URL` to identify an empty disposable database and refuse one containing users. SQLite tests do not replace those PostgreSQL checks.

`/health/live` is process liveness. The generic `/health/ready` retains a separate legacy inference contract; use `/api/v1/verified-inductive/status` and an actual successful inference for the active model runtime. The Audit operations screen is diagnostics, not a complete audit-log viewer.
