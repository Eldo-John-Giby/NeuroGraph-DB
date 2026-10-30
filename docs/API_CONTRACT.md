# Implemented API

The active API is FastAPI in `backend/app`, versioned under `/api/v1`. The old Express/Prisma prototype is not deployed. The running FastAPI OpenAPI document at `/openapi.json` is the machine-readable route schema; request/response types live in `backend/app/schemas.py` and route modules.

## Authentication and access

`POST /api/v1/auth/login`, `/refresh` and `/logout` manage signed access tokens and rotating HttpOnly refresh cookies. `GET /api/v1/auth/me` returns the authenticated account. Privileged account creation/listing and moderation enforce ADMIN server-side. Researchers can access their own analyses and feedback; admins can explicitly request all-user history. An external review author is not a login user.

## Main resources

| Resource | Implemented purpose |
|---|---|
| `/users` | Admin account creation and listing |
| `/reviews`, `/reviewers`, `/products` | Authenticated source-record catalogues, subject to the route's visibility rules |
| `/batch-analyses` | CSV intake, validation receipts, requester-specific history |
| `/batch-analyses/{id}` and its results/graph/score routes | Stored scores/evidence, graph projection and analysis processing |
| `/feedback` | Scoped human feedback CRUD and administrator resolution |
| `/model-versions`, `/preprocessing-versions`, `/inference-runs` | Registered versions and run provenance |
| `/graph-snapshots` | Available contexts and administrator batch-context permission |
| `/verified-inductive/status` | Deployed new-review model verification and recorded test metrics |
| `/verified-multimodal/status`, `/results`, `/predict` | Earlier raw known-node model status, saved results and known-node prediction |
| `/verified-baseline/status`, `/results`, `/predict` | Earlier structured MAT model status, saved results and known-node prediction |
| `/models/status`, `/graph-sync/status` | Legacy/runtime diagnostics; not substitutes for active model-specific status |

Check the exact route definitions before writing a client; the table groups related endpoints rather than replacing OpenAPI. Human feedback is implemented in `api/feedback.py`, uploads in `api/batches.py`, references/auth in `api/routes.py`, and verified historical adapters in their named modules.

## Error and integrity behavior

Errors use an envelope containing a code, message and request ID. Malformed CSV rows retain validation outcomes; conflicting existing review identities are rejected, while identical source records may be reused. Duplicate file retries can recover the prior receipt/run. New inference requires an eligible verified bundle and compatible approved context; unavailable or mismatched artifacts return explicit errors rather than synthetic scores.

The [matched comparison](benchmarks/README.md) is a recorded report served by Next.js at `/benchmarks/comparison.json`; it is not another prediction endpoint or a browser training job. No new backend model is selected by inspecting its test score.
