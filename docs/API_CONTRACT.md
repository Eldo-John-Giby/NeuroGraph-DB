# NeuroGraph-DB API Contract (Draft)

**Status:** Design contract only. No FastAPI routes or database schema are implemented here. Target stack is FastAPI + PostgreSQL + SQLAlchemy 2.x + Alembic with a React client. API behavior is a proposed contract, not a claim about the current Express/Prisma application.

## Contract principles

- JSON over HTTPS; versioned base path `/api/v1`; UTF-8; timestamps in UTC ISO 8601.
- PostgreSQL owns relational state. Client never connects directly to PostgreSQL or Neo4j.
- Login users are distinct from review authors. `user_id` identifies an app actor; `reviewer_id` identifies a source/domain review author.
- Predictions are **risk assessments**, not definitive fraud findings. `risk_score` is not a calibrated probability unless calibration is separately verified.
- Every returned prediction includes or links to its inference run, model version/checkpoint hash, preprocessing version/hash, graph snapshot/hash, and decision threshold.
- Historical results are read-only and distinguishable from new inference. Never fabricate placeholder scores, attention weights, or graph evidence.
- Current Phase 1 state has no compatible checkpoint. Model-backed inference returns a clear unavailable error until a verified model version, preprocessing contract, and matching graph snapshot are registered. Synthetic fallback is forbidden.
- Current known implementation is transductive. This draft only specifies known-review inference for review IDs present in the pinned graph snapshot. No unseen-review/new-node inference is promised.

## Authentication, authorization, and common behavior

Authentication uses a short-lived signed access token plus a rotating opaque refresh token. `session_tokens` stores only a digest of the refresh token and a digest of the access token JTI; never store or return token digests. Auth middleware validates signature/expiry and checks the matching non-revoked session row, so logout/revocation invalidates subsequent access. Refresh rotates credentials and revokes/replaces the prior session in one transaction. Passwords are Argon2id hashes per roadmap. Role authorization is resolved server-side from `users.role_id -> roles` and is not accepted from request body claims without signature/current-account validation.

Proposed initial role boundary:

| Operation | `RESEARCHER` | `ADMIN` |
|---|---:|---:|
| Read reviews, products, reviewers, model registry, completed runs/predictions | Yes, subject to data-access policy | Yes |
| Submit/update review feedback | Yes | Yes |
| Request known-review inference using a verified model | Yes | Yes |
| Create/update users and roles | No | Yes |
| Register/retire model versions or graph snapshots | No | Yes |
| Read audit and manage retry/terminal graph sync jobs | No | Yes |
| Delete provenance-bearing runs/predictions | No | No through ordinary API; privileged retention workflow only |

Authentication endpoints have throttling and generic login errors. For collection routes use `limit` (default 25, max 100), opaque or stable cursor pagination where practical, deterministic ordering, and filter validation. For inference-run, feedback, and user-originated graph-sync requests, `Idempotency-Key` is scoped to `(authenticated user_id, key)`; the same key used by another user is independent. Internal graph outbox deduplication uses a distinct global `source_event_key`. Mutations return resource IDs and timestamps. Use ETags/`If-Match` for concurrent edits where lost updates are possible.

## Endpoint catalog

| Method and path | Access | Purpose and contract |
|---|---|---|
| `POST /api/v1/auth/login` | Public, throttled | Validate credentials; return safe user profile and token/session. |
| `POST /api/v1/auth/refresh` | Authenticated by refresh credential | Rotate refresh token and access JTI; revoke prior `session_tokens` row and create replacement atomically. |
| `POST /api/v1/auth/logout` | Authenticated | Revoke the current session row; all tokens bound to it become invalid. Idempotent if already revoked. |
| `GET /api/v1/auth/sessions` | Authenticated | List current user's active session details only (created, last used, expirations); never return token digests. |
| `DELETE /api/v1/auth/sessions/{session_id}` | Authenticated | Revoke a session owned by current user; admin may revoke another user's sessions under explicit policy. |
| `POST /api/v1/auth/logout-all` | Authenticated | Revoke all active sessions for current user, including current session. |
| `GET /api/v1/auth/me` | Authenticated | Return current user and role from authoritative DB. |
| `GET /api/v1/roles` | Admin | List stable role definitions. |
| `GET /api/v1/users` / `POST /api/v1/users` | Admin | Paginated account administration/create; never return password hashes. |
| `GET /api/v1/users/{user_id}` / `PATCH /api/v1/users/{user_id}` | Admin or self-read | Read/update allowed account fields; deactivate/revoke sessions instead of routine hard delete. |
| `GET /api/v1/reviews` | Authenticated | Search/filter/paginate; filters may include source, reviewer, product, date range, ground-truth availability. Never expose ground truth to unauthorized roles if policy restricts it. |
| `POST /api/v1/reviews` | Authenticated | Create a review record; author (`reviewer_id`) is optional and independent from `submitted_by_user_id`. Imported identity uses `source_system` and `source_review_key`, which must be both null or both present. Creation alone does not imply a prediction. |
| `GET /api/v1/reviews/{review_id}` | Authenticated | Review detail with source IDs and summary of prediction/feedback availability. |
| `PATCH /api/v1/reviews/{review_id}` | Authenticated, policy-scoped | Update permitted review fields; audit changes. Prediction history is not silently rewritten. |
| `GET /api/v1/reviewers` / `POST /api/v1/reviewers` | Authenticated / privileged writes | List/create domain author records. Does not create login accounts. |
| `GET /api/v1/reviewers/{reviewer_id}` / `PATCH ...` | Authenticated / privileged writes | Read/update allowed author identity fields; preserve source-scoped external keys. |
| `GET /api/v1/products` / `POST /api/v1/products` | Authenticated / privileged writes | List/create products. |
| `GET /api/v1/products/{product_id}` / `PATCH ...` | Authenticated / privileged writes | Product detail/update. |
| `GET /api/v1/reviews/{review_id}/variants` | Authenticated | List stored variants and provenance. |
| `POST /api/v1/reviews/{review_id}/variants` | Admin/service | Register an approved, provenance-bearing variant; this does not claim a model attack study. |
| `GET /api/v1/models/status` | Public | Read database counts by provenance and verified-real eligibility; inference remains unavailable unless a compatible runtime is loaded. |
| `GET /api/v1/model-versions` | Authenticated | List model details, lifecycle status, and provenance; checkpoint URI may be hidden. |
| `GET /api/v1/preprocessing-versions` | Authenticated | List immutable preprocessing versions/checksums and status. |
| `POST /api/v1/preprocessing-versions` | Admin | Register a preprocessing manifest and canonical hash before model registration. |
| `POST /api/v1/model-versions` | Admin | Register checkpoint/`architecture_config` and a `preprocessing_version_id` FK; only verification can move it to `verified`. |
| `GET /api/v1/model-versions/{id}` | Authenticated | Read model version fields and verification state, excluding secret storage credentials. |
| `POST /api/v1/graph-snapshots` | Admin/service | Register immutable graph details/checksums and the complete `(review_id, split)` membership manifest atomically. Does not itself sync Neo4j. |
| `GET /api/v1/graph-snapshots/{id}` | Authenticated | Return identity, data/split-protocol/build versions, and storage status. |
| `PATCH /api/v1/graph-snapshots/{id}/batch-context-permission` | ADMIN | Explicitly permit/revoke a snapshot for future batch graph context; permission changes are audited. Only available snapshots can be permitted. |
| `POST /api/v1/batch-analyses` | Authenticated | Upload a bounded CSV, validate each row, persist accepted reviews/reviewer/product identities and all row outcomes transactionally, and return a blocked workflow record if scoring prerequisites are unavailable. |
| `GET /api/v1/batch-analyses/{batch_analysis_id}` | Owner or ADMIN | Return row counts, blockers, selected permitted snapshot, and optional real inference run link. |
| `GET /api/v1/batch-analyses/{batch_analysis_id}/results` | Owner or ADMIN | Paginate accepted/rejected row outcomes and accepted review details. Current blocked batches return `prediction: null`; future scoring must use persisted predictions and a real provenance-complete run. |
| `GET /api/v1/graph-snapshots/{id}/reviews` | Authenticated | Paginate snapshot members; optional `split=train|validation|test` filter reads `graph_snapshot_reviews`. |
| `POST /api/v1/inference-runs` | Authenticated | Current backend checks selected model DB provenance/lifecycle/checkpoint fields and verified preprocessing. Only `real` provenance is eligible for real inference; `synthetic_demo` cannot be verified or used for real scoring. A compatible runtime is not loaded, so current behavior is 503 without creating a run or prediction. |
| `GET /api/v1/inference-runs` | Authenticated | Paginated run history with model, graph, provenance, status, threshold and actor summaries. |
| `GET /api/v1/inference-runs/{run_id}` | Authenticated | Run state, counts, provenance and sanitized failure information. |
| `GET /api/v1/inference-runs/{run_id}/predictions` | Authenticated | Paginated predictions, each with joined provenance. |
| `GET /api/v1/reviews/{review_id}/predictions` | Authenticated | Historical predictions for a review, newest first, separated by run/model/snapshot. |
| `POST /api/v1/reviews/{review_id}/feedback` | Authenticated | Add a feedback record; feedback is not automatically ground truth. |
| `GET /api/v1/reviews/{review_id}/feedback` | Authenticated | Read feedback under role/privacy policy. |
| `GET /api/v1/analytics/high-risk-reviews` | Authenticated | Read-only equivalent of `vw_high_risk_reviews`; filter by run/model and paginate. “High risk” means predicted label under stored run threshold. |
| `GET /api/v1/analytics/product-risk` | Authenticated | Read-only product aggregate grouped by inference run to prevent mixing incompatible scores. |
| `GET /api/v1/graph-sync-jobs` | Admin | Inspect durable sync queue/status and retry history. |
| `POST /api/v1/graph-sync-jobs` | Admin/service | Queue a review-scoped `review_upsert`/`review_delete` with only `review_id`, or snapshot-scoped `snapshot_rebuild` with only `graph_snapshot_id`; DB checks reject mixed or empty scopes. User request uses user-scoped idempotency; internal outbox uses global source event key. |
| `POST /api/v1/graph-sync-jobs/{job_id}/retry` | Admin | Retry a failed idempotent projection job; cannot alter source prediction. |
| `GET /api/v1/audit-logs` | Admin | Paginated append-only audit events with redacted payloads. |
| `GET /health/live` | Public or internal | Process liveness only; no claim of dependency/model availability. |
| `GET /health/ready` | Internal/authorized | Readiness state for PostgreSQL and verified model artifact availability; report Neo4j separately if optional/degraded. |

Creation/administrative routes above are proposed. Their final role policy and data privacy scope require approval before implementation.

The batch-analysis routes above are implemented. They currently perform CSV validation and relational persistence only. Model scoring is blocked until a compatible verified runtime is loaded. A blocked batch is not inserted into `inference_runs`; that table requires real model, graph snapshot, and threshold provenance. The batch record's `inference_run_id` stays null, and per-row result `prediction` is null. Do not treat a batch status of `blocked` as an inference readiness state.

CSV contract: required columns `review_id, reviewer_id, product_id, rating, review_date, review_text`; `review_id`, `reviewer_id`, and `product_id` are source-system external keys. `source_system` is a multipart form field. Files are limited to 8 MiB/5,000 data rows; global encoding/header errors return 4xx, while row validation/source conflicts are persisted as per-row errors. See [BATCH_ANALYSIS.md](BATCH_ANALYSIS.md) for validation rules and scoring provider interfaces.

## Known-review inference request

`POST /api/v1/inference-runs`

Request:

```json
{
  "model_version_id": 17,
  "graph_snapshot_id": 6,
  "review_ids": [123, 456]
}
```

`Idempotency-Key: <client-generated opaque value>` is required for retry-safe client submission and is stored as `(requested_by_user_id, idempotency_key)`. IDs must resolve to existing rows included in the selected graph snapshot via `graph_snapshot_reviews`; each prediction's split is resolved from that membership row. Unknown/out-of-snapshot IDs return validation errors and do not trigger synthetic node insertion. The server checks selected-model DB provenance, lifecycle, checkpoint fields, and verified preprocessing status. Only `real` provenance is eligible for real inference; `synthetic_demo` models cannot be marked verified or used for real scoring. Even when DB records are eligible, this backend currently has no loaded scoring runtime and returns 503 without creating a run or prediction. The run/model composite FK prevents provenance mismatch.

Accepted response (`202 Accepted`):

```json
{
  "run_id": "4b82ed48-71d1-4ca3-b8a1-70dfab58c4ac",
  "status": "queued",
  "requested_count": 2,
  "completed_count": 0,
  "provenance": {
    "model_version_id": 17,
    "checkpoint_sha256": "<64 lowercase hex chars>",
    "preprocessing_version_id": 9,
    "preprocessing_version_key": "<registered immutable version>",
    "preprocessing_sha256": "<64 lowercase hex chars>",
    "graph_snapshot_id": 6,
    "graph_snapshot_sha256": "<64 lowercase hex chars>",
    "threshold": "<run threshold>",
    "threshold_source": "<validated manifest reference>"
  },
  "created_at": "2026-10-23T12:00:00Z"
}
```

The values above are schema examples/placeholders, not registered project artifacts or current thresholds. A failed run returns a terminal `failed` status and stable `failure_code`; it contains no prediction rows. The exact response status for synchronous CPU scoring may be `200`, but run persistence and provenance shape remain the same.

## Prediction response

```json
{
  "review_id": 1234,
  "run_id": "4b82ed48-71d1-4ca3-b8a1-70dfab58c4ac",
  "risk_score": "<score in [0,1]>",
  "predicted_label": "<boolean>",
  "threshold": "<threshold pinned to this run>",
  "interpretation": "model risk score; not a calibrated probability",
  "provenance": {
    "model_version_id": 17,
    "model_name": "<registered architecture>",
    "checkpoint_sha256": "<64 lowercase hex chars>",
    "preprocessing_version_id": 9,
    "preprocessing_version_key": "<registered immutable version>",
    "preprocessing_sha256": "<64 lowercase hex chars>",
    "graph_snapshot_id": 6,
    "graph_snapshot_sha256": "<64 lowercase hex chars>",
    "split_protocol_key": "<registered split protocol>",
    "review_split": "<train | validation | test>"
  },
  "attention": null,
  "graph_status": "<not requested | available | unavailable | stale>"
}
```

All scores shown are illustrative JSON shape examples, not model outputs. `attention` is null unless the selected verified model genuinely emits reproducible attention weights. Attention is not causal explanation. Graph status must describe actual graph availability; Neo4j outage must not be presented as completed graph analysis.

## Views and analytics contract

- `vw_high_risk_reviews`: join reviews to predictions and runs; select `predicted_label = true`; expose run/model/checkpoint/preprocessing/snapshot/threshold fields. Clients must choose or receive an explicit run to avoid ambiguous latest-model results.
- `vw_product_risk_summary`: group by `(product_id, inference_run_id)` and report scored-review count, flagged count, score aggregates, plus run provenance. Do not average scores across runs/checkpoints/snapshots.
- Result-set ordering and pagination are deterministic. All aggregates exclude failed runs and clearly mark partial runs.
- Views are read-only. Writes go through resource APIs/SQLAlchemy transactions or the explicitly approved procedure.

## Transactions, audit, and error contract

- Inference request transaction: validate model/snapshot/review IDs, insert run, and enqueue work atomically. Worker saves prediction batches idempotently and transitions run status atomically; a partial failure remains visible.
- Session transaction: login creates a session row containing token digests; refresh rotates credentials and revokes/replaces the prior row; logout marks the current row revoked. Access authentication rejects revoked/expired session rows.
- Feedback transaction: insert feedback and append its audit event in one transaction.
- CRUD transaction: mutate row plus audit record; trigger captures allowlisted field diffs. Audit rows are append-only to the application role.
- Graph sync transaction: update PostgreSQL job state; Neo4j is outside the SQL transaction. User-originated retries use `(user_id, idempotency_key)`; outbox events deduplicate using a separate global `source_event_key`. Report projection lag/failure separately.
- Standard error body:

```json
{
  "error": {
    "code": "model_unavailable",
    "message": "No verified checkpoint is available for the requested model version.",
    "request_id": "9d9187de-31bf-4b6a-98c8-8225f5fd82b4",
    "details": {}
  }
}
```

Suggested HTTP mapping: `400` malformed request, `401` unauthenticated, `403` forbidden, `404` missing resource, `409` idempotency/state conflict, `422` invalid fields or incompatible model/data contract, `429` rate limited, `503` verified checkpoint or required dependency unavailable, `500` unexpected sanitized internal error. Never include SQL, stack traces, secrets, checkpoint credentials, password hashes, or full raw review text in errors.

## ORM and API query conventions

SQLAlchemy 2.x models follow the ERD FKs/uniques/checks. Use Python attributes `architecture_config` and `review_metadata` to avoid Pydantic and SQLAlchemy reserved namespaces. SQLAlchemy `select()` is preferred over dynamically interpolated SQL; all user values are bind parameters. Use `selectinload`/explicit joins for bounded relations, not unbounded eager collections. Analytics use database views or explicit grouped queries. Alembic migrations own DDL, including indexes, view definitions, audit triggers, and approved procedure definitions. API integration tests must verify SQLAlchemy transactions, uniqueness/FK/check failures, RBAC, idempotency, and rollback behavior before a route is called production-ready.

## Backup/restore operational contract

The service's operational documentation will define encrypted PostgreSQL custom-format backups (`pg_dump -Fc`) and a restore procedure (`pg_restore`) validated against a clean database. Record dump checksum, schema migration head, timestamp, and retention window. Checkpoint and graph artifact storage is backed up/versioned separately and verified against stored SHA-256 values. Restore drills must verify relational counts/FKs, a known saved prediction's provenance rows, and the documented rebuild/reconciliation of Neo4j. This contract does not claim such tooling exists today.

## Out of scope for this contract

- No endpoints, migrations, SQLAlchemy classes, authentication code, or UI changes are created here.
- No unseen-review model inference or graph insertion is promised.
- No model score, attention value, graph fact, checkpoint, or performance metric is supplied by these examples.
- Final API roles, review data visibility, retention, account-role multiplicity, synchronous vs queued inference, and review-submission workflow need team review before implementation.

