# NeuroGraph-DB

A database-backed review investigation app with verified graph-model inference. Users upload a CSV, receive risk scores, and reopen their own saved analyses. PostgreSQL stores users, reviews, results and audit records; Neo4j supplies relationship evidence.

[Open the live application](https://frontend-three-snowy-10.vercel.app) · [Rubric and evidence](docs/submission/README.md) · [Complete ER diagram](docs/submission/ERD.md) · [Data dictionary](docs/submission/DATA_DICTIONARY.md)

Preparing to present? Start with the [plain-English viva guide](docs/defense/BEGINNER_VIVA_GUIDE.md), which explains the exact dataset, train/test split, model, scores, database roles and files to show.

Access is by an administrator-provisioned account. Demo credentials are shared privately, never in this repository. The app is a student research demonstration; a model flag is an investigation signal, not proof of fraud.

## What to try

1. Sign in and open **Model results** for the final model's chronological evaluation.
2. Open **Upload & analyze**, download the sample CSV, and upload it. The application selects the compatible historical context.
3. Open **Products & history** to revisit saved results without rerunning the model. The result summary separates flagged, not flagged, unscored and rejected rows. Search/filter the rows, open full review text and context, record feedback, or download all results as CSV. Identical file retries recover your prior receipt.
4. Use **Review feedback** to create, edit or remove a submitted investigation note. An administrator can triage or resolve it. Feedback never overwrites predictions.
5. Open **Model comparison** for the shared-test results and all historical experiments. Use **Example investigation** for clearly marked synthetic case studies.

Researchers see their own upload histories and private records. Administrators explicitly select all-user history and have separate administration menus. Authentication and access checks also run on the server.

## Comparable model results

[Open Model comparison](https://frontend-three-snowy-10.vercel.app/benchmarks) to compare four architectures on exactly the same **9,436 chronological test reviews**. The page has selectable seeds and metrics, ROC/precision–recall curves, missing-context sensitivity, downloadable evidence and all three historical experiment records.

The shared source has 47,176 labelled real historical reviews: 28,305 training, 9,435 validation and 9,436 test. Every arm uses the same membership and validation-selection rule. Text-enabled arms share the frozen RoBERTa vectors; graph-enabled arms share the 14 features and causal relations. These are controlled architecture ablations with intentionally different modalities and parameter counts.

### Seed 42 and the deployed checkpoint

| Model | ROC-AUC | PR-AUC / AP | Macro F1 |
|---|---:|---:|---:|
| Text only | 0.7835 | 0.4035 | 0.6475 |
| Graph only | 0.7373 | 0.2685 | 0.5974 |
| Text + graph concatenation | 0.8109 | 0.4213 | 0.6592 |
| NeuroGraph | 0.8105 | 0.4211 | 0.6624 |

The NeuroGraph row is the **same sealed seed-42 checkpoint used for live CSV scoring**. Its validation-selected cutoff is 0.7870707071. It has the highest seed-42 macro F1; concatenation has slightly higher seed-42 ROC-AUC and average precision.

### Mean and sample SD across seeds 42, 43 and 44

| Model | ROC-AUC | PR-AUC / AP | Macro F1 |
|---|---:|---:|---:|
| Text only | 0.7821 ± 0.0015 | 0.4011 ± 0.0024 | 0.6499 ± 0.0022 |
| Graph only | 0.7389 ± 0.0016 | 0.2687 ± 0.0020 | 0.5983 ± 0.0020 |
| Text + graph concatenation | 0.8110 ± 0.0034 | 0.4222 ± 0.0099 | 0.6628 ± 0.0034 |
| NeuroGraph | 0.8084 ± 0.0033 | 0.4154 ± 0.0162 | 0.6589 ± 0.0033 |

Both combined models outperform the single-modality arms in these runs. Concatenation has the highest three-seed mean; the experiment does not establish a consistent gain from NeuroGraph's attention/gate over simple concatenation. SD measures initialization variation, not a confidence interval. The deployed checkpoint was originally GPU-trained; added runs use CPU under the same optimization controls. No production model was replaced based on its test score.

ROC-AUC is not classification accuracy. PR-AUC uses average precision. User CSVs without ground-truth labels have predictions, not measured accuracy. This is a retrospective evaluation on one existing historical holdout with imperfect Yelp filtering labels. Synthetic examples and old near-perfect fixture scores are not real-data benchmark evidence.

The structured MAT baseline (0.9331 ROC-AUC), earlier raw known-node model (0.8439), and deployed temporal model (0.8105) are all visible in **Earlier experiment records** below the matched charts. Their different representations/protocols exclude them from a shared ranking. See the [complete method and evidence](docs/benchmarks/README.md), [model card](docs/MODEL_CARD.md) and [provenance audit](docs/MODEL_AUDIT.md).

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
node --test tests/*.test.cjs
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

[GitHub Actions](https://github.com/Eldo-John-Giby/NeuroGraph-DB/actions) automatically tests the real FastAPI backend, migrations on PostgreSQL, frontend authentication/lint/build and the deployable Docker image. It uses standard Linux runners on the public repository. Hosted jobs skip the private submission mirror to avoid metered allowance use. No workflow contains cloud credentials or performs an unguarded paid deployment.

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

The implemented workflow is CI (automatic tests and builds); production release is a separate explicit CLI step, not automatic CD. See [the pipeline and bonus explanation](docs/CI_AND_RELEASE.md).

## Administration and independent review

The **Model registry** records model/checkpoint identity, preparation versions and scoring jobs, and checks the current new-review runtime. It is read-only provenance, not another model leaderboard or a model-switching control. The **Reviewer catalog** maps source author keys to internal author IDs and opens their visible reviews. It does not assign account-level fraud scores; source authors are distinct from application login users. Both screens are administrator UI tools.

An [independent review brief](docs/review/INDEPENDENT_REVIEW.md) lists the evidence, files, live walkthrough and scientific/security questions for a separate review. It does not claim an external review has already taken place.
