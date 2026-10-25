# CSV Batch Analysis

## Current capability and safety boundary

The API accepts and validates CSV review batches, records a durable batch status and one result row per CSV record, resolves reviewers/products, and persists valid reviews. Scoring remains unavailable: the repository has no compatible verified checkpoint/runtime bundle. A blocked batch therefore has `inference_run_id: null` and contains no score or attention value. It must not manufacture an `InferenceRun`: the approved relational schema requires an `InferenceRun` to reference an actual model version, graph snapshot, and threshold. A future worker creates that row only after resolving real verified provenance and a loaded compatible runtime.

Batch analysis records are workflow/import records, not model inference records. The batch response names its state `blocked` and gives explicit reasons. `GET /api/v1/models/status` remains the separate source for model runtime availability.

## CSV contract

Multipart form fields:

- `file`: UTF-8 or UTF-8-with-BOM CSV, maximum 8 MiB and 5,000 data rows.
- `source_system`: required namespace for incoming source identifiers (1–100 characters).
- `historic_graph_snapshot_id`: optional snapshot selection. If supplied, it must exist, be available, and have been explicitly permitted by an administrator for batch context.

Required headers are `review_id, reviewer_id, product_id, rating, review_date, review_text`. Extra columns are ignored. `review_id`, `reviewer_id`, and `product_id` are treated as source-system external keys, not internal database integers. They are resolved/created using `(source_system, external key)`. `review_id` maps to `reviews.source_review_key`. `rating` must be an integer 1–5. `review_date` must be ISO-8601; a date or timezone-free timestamp is interpreted as UTC. Text must be nonempty. Duplicate review keys within the upload or already present under the same source are rejected by row. The source review uniqueness constraint remains the final race-safe guard.

Global file/header errors return structured 4xx errors without creating a batch. Row-level errors do not reject other rows: the batch and all row outcomes are committed in one transaction, valid rows get reviewer/product/review records, and invalid rows retain their row number, source review key when parseable, and structured field errors. The upload itself is not retained; its SHA-256 is stored for provenance.

## Endpoints

| Method and path | Behavior |
|---|---|
| `POST /api/v1/batch-analyses` | Authenticated multipart CSV intake; returns batch ID/key, row counts, status, permitted snapshot selection, upload SHA-256, blockers, and optional future inference-run ID. |
| `GET /api/v1/batch-analyses/{batch_analysis_id}` | Owner or ADMIN can retrieve counts, status, blockers, snapshot, and optional inference-run ID. |
| `GET /api/v1/batch-analyses/{batch_analysis_id}/results?limit=25&offset=0` | Owner or ADMIN gets paginated accepted/rejected row outcomes and accepted review fields. `prediction` is null while no persisted inference exists; no fake scores are returned. |
| `PATCH /api/v1/graph-snapshots/{snapshot_id}/batch-context-permission` | ADMIN explicitly permits/revokes a snapshot for future batch context use; permission changes are audited. Unavailable snapshots cannot be permitted. |

Pagination uses `limit` 1–100 and nonnegative `offset`. Batch status is one of `blocked`, `queued`, `running`, `completed`, `partial`, `failed`, or `validation_failed`. With at least one accepted row and no verified bundle, status is `blocked` with `verified_model_bundle_not_registered`; if a verified model/preprocessor registry candidate exists but no compatible runtime is loaded, the blocker is `verified_scoring_runtime_not_loaded`. An unselected history snapshot adds `historic_graph_snapshot_not_selected`. A batch with no accepted rows is `validation_failed`.

## Persistence and transaction boundary

- `batch_analyses` stores requester, source namespace, checksum, counts, permitted historical snapshot selection, status/blockers, and an optional one-to-one link to a real `inference_runs` row.
- `batch_analysis_rows` stores one ordered outcome per input record, the optional accepted `review_id`, parse/validation errors, and the incoming review key. Accepted rows reference normal `reviews`; rejected rows have no review FK.
- A single SQLAlchemy transaction persists the batch, row outcomes, and all accepted review/reviewer/product rows plus an audit event. Integrity conflicts roll back the batch transaction and return a conflict response.
- Existing reviewer/product identities are resolved under the provided `source_system`. This does not merge identities across different source namespaces.
- The snapshot permission flag defaults false, including for preexisting snapshots after migration. Only an ADMIN action can set it through the API, and the selected snapshot must be available.

## Batch scoring interfaces and label-free relation builder

`backend/app/services/batch_csv.py` defines label-free `BatchReviewInput` and provider protocols. A future verified runtime must assemble all components from one immutable, compatible manifest:

1. **Semantic embedding provider:** a pinned RoBERTa model/tokenizer revision and preprocessing checksum; it returns finite vectors with the dimension required by the verified architecture (the audited NeuroGraph config expects 768). The current mock graph's semantic vectors were generated from random data; they are not RoBERTa embeddings.
2. **Behavioral feature provider:** returns a finite matrix ordered by the preprocessing manifest, with exact feature names, definitions, temporal cutoffs, null handling, and fitted scaler identity. The existing scaler names `log_char_length`, `rating`, `prod_avg_rating_dev`, `user_avg_rating_dev`, `log_user_review_count`, and `log_prod_review_count` describe six candidate fields. The remaining 26 are named `proxy_feature_6` through `proxy_feature_31`; their semantics are not established. The current `ml/mock_data.py` generates metadata synthetically. No current batch feature implementation maps this 32-column vector, and no feature may be represented as checkpoint-compatible until an owner supplies and verifies the exact mapping/scaler.
3. **Relation builder:** `backend/app/services/batch_graph.py` implements `LabelFreeBatchRelationBuilder`. Node order is uploaded rows followed by permitted historical rows; RUR links equal reviewer IDs, RSR links equal product and rating, and RTR links reviews for the same product within a configurable window (default 30 days), following the meanings stated in `data_pipeline/STATS.md`. Edges are bidirectional, omit self-edges, and cap selected neighbors at 50 per uploaded node/relation by default. Only edges touching uploaded nodes are returned; historical-to-historical edges remain from the selected graph snapshot. Output uses schema version `batch-rur-rsr-rtr-v1`. This is a new deterministic batch implementation, not one verified as compatible with an existing checkpoint.
4. **Scoring runtime:** requires a verified checkpoint SHA-256, architecture/config checksum, preprocessing version/checksum, permitted graph snapshot/artifact checksum, supported inference mode, and validated threshold. It must verify provider dimensions/order/checksums before model invocation. It persists predictions and the provenance-complete inference run transactionally. Attention is stored only if the real model emits it.

`load_permitted_historic_context` checks that a snapshot is available and explicitly permitted, then queries membership for exactly the requested split. Its SQL projection selects review ID, reviewer ID, product ID, rating, timestamp, and text, and omits `ground_truth_label` and `label_source`. `BatchReviewInput` also has no label field. Tests exercise an uploaded review linked to historic context and verify split filtering.

No unseen-review inductive capability is claimed. Batch scoring remains disabled until the complete checkpoint/config/preprocessing/graph/threshold tuple and an executable compatible runtime are verified. The API persists uploaded rows; the relation builder can construct label-free in-memory edges. No embeddings, behavioral vectors, predictions, or attention values are currently produced.

## Alembic and verification

Migration `0002_batch_analyses` adds the two batch tables and the default-false graph snapshot permission field. Apply it with `cd backend && alembic upgrade head` after configuring PostgreSQL. The API tests exercise malformed/header/row validation, partial acceptance, reviewer/product resolution, pagination/ownership, migration model constraints, and the blocked-model behavior with SQLite fixtures. These tests do not establish PostgreSQL or Neo4j integration.

Migration `0004_synthetic_campaigns` adds synthetic-only campaign, member, and campaign-review tables, indexes, FK/check constraints, and graph-snapshot provenance. It follows `0003_add_provenance_tracking`.

## Deterministic synthetic restaurant campaign

`backend/scripts/seed_demo_batch.py` now seeds a fixed, provenance-scoped restaurant scenario instead of the former generic set of 200 demo reviews. It refuses to start unless `DEMO_MODE=true` is explicitly set. Reviews, reviewers, and products use `source_system=synthetic_demo`; campaign, membership, and campaign-review rows carry `provenance=synthetic_demo`. The script writes no ground-truth labels, model outputs, attention values, checkpoint, or verified model. It does not modify real-provenance model eligibility.

The main target is **Harbor Table · synthetic restaurant**. Its comparison window contains 28 reviews over six days. The attack window contains 36 one-to-two-star reviews over 36 hours: 30 one-star and 6 two-star, from 24 external reviewer accounts. Several accounts post more than once during the attack window; eight attack participants also occur in a separate earlier, concentrated Cedar Spoon synthetic campaign. Attack text repeats short negative phrases while retaining distinct per-review text, and timestamps are deliberately close together. All seeded timestamps are UTC. This creates inspectable reviewer, product/rating, timing, text, and prior-campaign overlap evidence. These generated records do not describe actual restaurants or people.

The seed uses fixed dates and stable source keys, so rerunning a complete seed is idempotent. A partial/conflicting target scenario causes a refusal instead of a silent repair. When it encounters the old generic seed's exact source-key/run identity, it removes only those old demo rows after checking for non-seed batch, feedback, campaign, and prediction references; otherwise it stops. It also removes the old synthetic model/preprocessing/snapshot records only when they have no remaining run or batch references. No database was changed merely by editing this script.

### Synthetic campaign analytics API

All routes require normal API authentication, return only campaigns with `provenance='synthetic_demo'`, and use review/product/reviewer records with `source_system='synthetic_demo'`.

| Method and path | Response contents |
|---|---|
| `GET /api/v1/synthetic-campaigns/{campaign_key}/summary` | Campaign and restaurant identity, both windows, attack review/reviewer counts, one-star count, attack mean, burst rate, comparison count, and exact reviewer overlap with the linked prior campaign. |
| `GET /api/v1/synthetic-campaigns/{campaign_key}/rating-over-time` | Per-day review counts and observed mean rating for the target restaurant through the attack-window end. |
| `GET /api/v1/synthetic-campaigns/{campaign_key}/rating-comparison` | Observed mean for all synthetic restaurant reviews in the attack window; scenario-adjusted mean after excluding campaign-linked attack review IDs; and target restaurant comparison-window mean. |
| `GET /api/v1/synthetic-campaigns/{campaign_key}/volume-by-day` | Per-day target-restaurant volume and rating for the comparison-through-attack period, labeled by window, plus the daily-volume ratio. |
| `GET /api/v1/synthetic-campaigns/{campaign_key}/members?limit=25&offset=0` | Paginated attack participants with campaign-linked review keys, times, text, ratings, one-star count, prior-campaign overlap, and stored evidence notes. |

Members pagination accepts `limit=1..100` and nonnegative `offset`. Missing campaign keys return 404; real-provenance campaigns are not served by these synthetic-only routes.

### Metric definitions and provenance limits

- **Observed attack-window rating** is the arithmetic mean of non-null `reviews.rating` for synthetic-source reviews on the target restaurant inside the declared attack bounds.
- **Scenario-adjusted attack-window rating** is the arithmetic mean over the same target, source, time bounds, and non-null ratings after excluding review IDs linked to the campaign with period `attack`. This is a transparent what-if comparison against stored scenario membership. It is not an estimate of a true counterfactual, a calibrated fraud-risk adjustment, or a model prediction.
- **Rating over time** groups target restaurant reviews by database date and computes `COUNT(review_id)` and `AVG(rating)`.
- **Daily volume comparison** labels dates in the declared comparison or attack windows, computes window review totals divided by inclusive calendar-day counts, and returns attack daily volume divided by comparison daily volume. A zero comparison count yields a null ratio.
- **Campaign evidence** is relational evidence in the seed: shared reviewer IDs between campaign membership records, review timestamps, ratings, product identity, and the actual stored text. The API does not infer coordination from a trained model.

Analytics responses carry synthetic provenance or an explicit synthetic-only interpretation. No model score or attention is used in these formulas. Do not label the scenario-adjusted value as a corrected restaurant rating, fraud probability, or recovered ground truth.

### Local demo flow

1. Apply migrations: `cd backend && alembic upgrade head`.
2. Start local API and PostgreSQL using the repository's documented development startup path.
3. Seed from the repository root: `DEMO_MODE=true python backend/scripts/seed_demo_batch.py` (with backend dependencies installed and `DATABASE_URL` configured).
4. Sign in with an existing application user and request the summary, rating timeline/comparison, daily volumes, and member evidence routes above.

The fixture is for UI and SQL demonstration only. Campaign membership is declared by the seed, not discovered by ML. Synthetic values are not real-world evidence, evaluation data, or model performance. No live PostgreSQL execution or seed run is claimed by this documentation change.

## Synthetic campaign Neo4j projection

`backend/app/services/neo4j_synthetic_projection.py` implements an explicit one-campaign projection worker. It loads the main campaign and its linked prior campaign from PostgreSQL, then includes only campaign-linked reviews, synthetic-source reviewers, synthetic-source restaurants, and provenance-tagged campaign evidence. It refuses the projection if any linked entity is missing or outside `synthetic_demo`. It does not inspect model versions, fraud predictions, or attention.

The worker idempotently `MERGE`s nodes by stable `key` and relationships by typed endpoints, after ensuring unique-key constraints for the four node labels. It writes `Restaurant`, `Reviewer`, `Review`, and `Campaign` nodes, and `TARGETS`, `HAS_REVIEW`, `AUTHORED`, `ABOUT`, `PARTICIPATES_IN`, `PREVIOUS_CAMPAIGN`, and `OVERLAPS_WITH` relationships. Evidence notes, review dates/ratings/text, membership type, and shared external reviewer keys remain sourced from PostgreSQL. Every projected node and relationship carries `provenance=synthetic_demo` and scenario campaign keys.

Configure `NEO4J_URI` and, when required by the server, `NEO4J_USERNAME` and `NEO4J_PASSWORD`. Install the backend package dependency `neo4j>=5.24,<7`. After migrating and seeding PostgreSQL, run:

```sh
cd backend
python scripts/project_synthetic_campaign.py --campaign-key harbor-table-review-bombing-seed-42
```

This command is the worker entry point; it does not run automatically and it does not mutate PostgreSQL. Re-running it upserts the same projection. It is separate from the general `graph_sync_jobs` queue, which remains unimplemented as a Neo4j worker.

The authenticated, read-only endpoint `GET /api/v1/synthetic-campaigns/{campaign_key}/graph` reads the existing projection from Neo4j. It returns `provenance=synthetic_demo`, `source=neo4j_synthetic_demo_projection`, and `model_inference_used=false`. If Neo4j is unconfigured/unreachable it returns HTTP 503 with `neo4j_unavailable`; if the campaign exists in PostgreSQL but no projected nodes exist, it returns HTTP 409 with `campaign_graph_not_projected`. It never responds with a fabricated empty graph on connection failure. No live Neo4j connection or traversal has been verified by the automated tests.
