# NeuroGraph-DB

A database-backed review investigation app with verified graph-model inference. Users upload a CSV, receive risk scores, and reopen their own saved analyses. PostgreSQL stores users, reviews, results and audit records; Neo4j supplies relationship evidence.

[Open the live application](https://frontend-three-snowy-10.vercel.app) · [Rubric and evidence](docs/submission/README.md) · [Complete ER diagram](docs/submission/ERD.md) · [Data dictionary](docs/submission/DATA_DICTIONARY.md)

Access is by an administrator-provisioned account. Demo credentials are shared privately, never in this repository. The app is a student research demonstration; a model flag is an investigation signal, not proof of fraud.

## What to try

1. Sign in and open **Model results** for the final model's chronological evaluation.
2. Open **Upload & analyze**, download the sample CSV, and upload it. The application selects the compatible historical context.
3. Open **Products & history** to revisit the saved scores and graph without rerunning the model. Identical file retries recover your prior receipt.
4. Use **Review feedback** to create, edit or remove a submitted investigation note. An administrator can triage or resolve it. Feedback never overwrites predictions.
5. Use **Benchmark evidence** for known-node experiments and **Example investigation** for clearly marked synthetic case studies.

Researchers see their own upload histories and private records. Administrators explicitly select all-user history and have separate administration menus. Authentication and access checks also run on the server.

## Verified model results

| Evaluation | ROC-AUC | F1 macro | PR-AUC | Scope |
|---|---:|---:|---:|---|
| Final inductive model | 0.8105 | 0.6624 | 0.4211 | 9,436 chronological test reviews; new reviews scored against permitted historical context |
| Multimodal benchmark | 0.8439 | 0.6860 | See verified run record | Known nodes in the frozen YelpChi graph; a different evaluation protocol |

The inductive threshold is 0.7870707071, selected on validation data. Scores on unlabelled user CSVs are predictions, not measured accuracy. Verification records, checksums and reproduction commands are in [docs/runs](docs/runs), [the inductive runbook](docs/INDUCTIVE_YELPCHI_RUNBOOK.md) and [the multimodal runbook](docs/RAW_YELPCHI_MULTIMODAL_RUNBOOK.md). Synthetic examples are never presented as measured model results.

## Stack and architecture

| Part | Deployed implementation |
|---|---|
| Frontend | Next.js 15.5, React 18, TypeScript, Vercel Hobby |
| Backend | FastAPI, Python 3.11, SQLAlchemy 2, Alembic |
| Primary database | PostgreSQL 16, 23 domain tables, two aggregate views |
| Graph projection | Neo4j 5, Cypher |
| Model runtime | CPU PyTorch, PyTorch Geometric, pinned RoBERTa encoder |
| Security | Argon2 password hashes, JWT access tokens, rotating HttpOnly refresh cookies, ADMIN and RESEARCHER roles in one users table |
| Infrastructure | Docker Compose, Caddy HTTPS, AWS CloudFormation and SSM on an AWS Free account plan |

```mermaid
flowchart LR
    User[Researcher or administrator] --> Web[Next.js on Vercel]
    Web -->|same-origin API proxy| API[FastAPI on AWS]
    API --> ORM[SQLAlchemy]
    ORM --> PG[(PostgreSQL system of record)]
    API --> ML[Verified CPU graph model]
    API --> NG[(Neo4j projection)]
    ML --> PG
```

`backend/` is the current API. `db-dashboard/backend/` is an earlier Express/Prisma prototype and is **not** deployed or counted as the course database. `viz/` and `data_pipeline/sql/` retain earlier research utilities. The authoritative app schema is Alembic plus `backend/app/models.py`.

## Run locally

Requirements: Python 3.11+, Node.js 22+, Docker with Compose, and Git. PostgreSQL and Neo4j can run locally with the provided configuration. Verified ML bundles are separately distributed research artifacts; a fresh clone does not contain those large private bundles.

```sh
git clone https://github.com/Eldo-John-Giby/NeuroGraph-DB.git
cd NeuroGraph-DB
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch>=2.6,<3'
python -m pip install './backend[test,deploy]'
cp backend/.env.example backend/.env
```

Set `DATABASE_URL`, a random `JWT_SECRET_KEY` of at least 32 characters, and local service credentials in the ignored `backend/.env`. For HTTP localhost only, set `COOKIE_SECURE=false`. Set `CORS_ORIGINS=http://localhost:3000`. Never use production passwords locally or commit an `.env` file.

For a local PostgreSQL container, supply `POSTGRES_PASSWORD` in your shell or an ignored Compose environment file, then run:

```sh
docker compose -f data_pipeline/docker-compose.postgres.yml up -d
cd backend
set -a
source .env
set +a
alembic upgrade head
python scripts/seed_roles.py
# Set ADMIN_PASSWORD and RESEARCHER_PASSWORD privately before provisioning.
python scripts/seed_users.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd db-dashboard/frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. API documentation is at `http://localhost:8000/docs`. The frontend proxies `/api/v1` to `BACKEND_URL`, defaulting to localhost:8000.

For verified scoring, obtain the exact bundles identified in `docs/runs`, place them under the documented `artifacts/verified_*` paths, and follow the registration runbooks. The application fails closed when files, hashes, encoder revisions or historical contexts do not match. Database, login and CRUD tests do not require full model downloads.

## Database features and tests

- All 23 application tables appear in the generated ERD and dictionary, including primary/foreign keys, constraints and indexes.
- SQLAlchemy performs application CRUD, scoped joins, filtering, pagination and transactions.
- Alembic migration `0007_database_features` installs `vw_batch_analysis_summary`, `vw_product_review_summary`, the redacted feedback audit trigger and `resolve_review_feedback` procedure.
- The administrator feedback page reads actual aggregate views. Admin moderation invokes the procedure; the trigger audits insert/update/delete inside the same transaction.
- [Normalization analysis](docs/submission/NORMALIZATION.md) distinguishes normalized entity data from immutable event snapshots and explicitly recorded operational redundancy.

```sh
cd backend
PYTHONPATH=..:. pytest
# To include PostgreSQL-only tests, TEST_POSTGRES_URL must point to an EMPTY
# DISPOSABLE database. The tests refuse a database already containing users.
TEST_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@localhost/EMPTY_TEST_DB' PYTHONPATH=..:. pytest tests/test_postgres_features.py
cd ../db-dashboard/frontend
node --test tests/auth-refresh.test.cjs
npm run lint
npm run build
```

Native recovery drill, using the local PostgreSQL container:

```sh
python3 scripts/verify_backup.py --container neurograph_db --user neuro --database neurograph
```

This runs `pg_dump -Fc` and `pg_restore` into a new disposable database, checks table counts and prediction provenance, then removes only that disposable database. Dumps and credentials remain ignored. See [executed evidence](docs/submission/evidence/backup-restore.json).

## Deployment and CI

The live frontend uses Vercel Hobby. The backend, PostgreSQL and Neo4j share one AWS server. PostgreSQL is cloud-hosted here; it is **not a managed database service**. Cloud deployment instructions and scripts are in [deploy/aws](deploy/aws/README.md). Before AWS mutations, `scripts/aws_free_plan.py` checks the intended account, FREE/ACTIVE status, expiry and remaining credit. The Free account plan is time- and credit-limited; this is not indefinite free hosting. No paid-plan upgrade is automated.

[GitHub Actions](https://github.com/Eldo-John-Giby/NeuroGraph-DB/actions) tests the real FastAPI backend, migrations on PostgreSQL, frontend authentication/lint/build and the deployable Docker image. It uses standard Linux runners on the public repository. Hosted jobs skip the private submission mirror to avoid metered allowance use. No workflow contains cloud credentials or performs an unguarded paid deployment.

The default Vercel address and the backend's `sslip.io` hostname are provider hostnames. We do **not** claim the rubric's custom-domain bonus without an independently configured domain. No Docker Hub login is currently configured; the image builds and runs locally and on the server, but Docker Hub publication is not claimed.

## Repository map

```text
backend/                  FastAPI, SQLAlchemy models, Alembic, tests
db-dashboard/frontend/    Current Next.js application
ml/                       Graph models, training and evaluation scripts
data_pipeline/            Research ingestion, graph and embedding preparation
viz/                      Earlier research visualization and Cypher examples
deploy/aws/               CloudFormation, Compose, HTTPS and deployment notes
scripts/                  Deployment guards, backup drill and schema export
docs/submission/          Current rubric evidence, schema and faculty demo guide
docs/runs/                Verified training/evaluation run records
```

Team: Avaneesh Chavan (data and application integration), Eldo John Giby (ML), Anubhav Bhattacharya (visualization and documentation). Course submission identifiers and instructor access details are distributed privately. The private submission mirror preserves project history, `main` and `dev`; the public team source remains available for demonstration and review.

This is an academic research system. It does not establish review fraud as fact, does not include guaranteed uptime or autonomous retraining, and does not claim every model improvement proposed in historical planning documents has been implemented. The current submission evidence takes precedence over archived phase plans.
