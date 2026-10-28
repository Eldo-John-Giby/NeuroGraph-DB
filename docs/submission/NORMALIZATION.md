# Normalization and relational design

The authoritative ERD and data dictionary are generated from the same SQLAlchemy metadata as the 23-table application. Historical 18-table diagrams are retained as design history, not used as the final schema.

## Functional dependencies and decomposition

| Entity group | Keys and dependencies | Decomposition rationale |
|---|---|---|
| roles, users, session_tokens | role_id -> role attributes; user_id and normalized email -> user attributes; session UUID -> token digests, expiry and revocation | Roles are not repeated as separate administrator/researcher tables. Credentials and session state have separate lifecycles. Email normalization is a checked representation of one identity, not another account. |
| reviewers, products, reviews | Internal IDs and source/external-key pairs identify source entities. review_id -> author, product, source key, rating, text and time | A review contains author/product foreign keys, not copies of names or catalogs. The login user and external review author are different entities. |
| review_variants, review_feedback | variant ID and (review_id, variant_key) -> variant details; feedback_id -> review, author, comment, proposed label and status | Variants and human feedback are many-to-one child records, not repeating columns on reviews. Proposed corrections do not overwrite immutable model output. |
| preprocessing_versions, model_versions | preprocessing ID/hash -> preprocessing configuration; model ID/version -> checkpoint, preprocessing FK, contract and threshold | Preprocessing configuration is not repeated in each model or result. Files are referenced by version and checksums. JSON configuration is an opaque versioned artifact, not a substitute for relational identity. |
| graph_snapshots, graph_snapshot_reviews | snapshot ID/key/hash -> graph identity; (snapshot_id,review_id) -> node index/split | The many-to-many membership and split belong to a junction table, not comma-separated review lists. |
| inference_runs, fraud_predictions | run ID -> pinned model, graph, requested actor, threshold and execution; (run_id,review_id) -> score, label and attention | Predictions are observations of a particular run. Threshold is an immutable run parameter, allowed to differ from the model recommendation; the decision label belongs to that run. |
| batch_analyses, batch_analysis_rows | batch ID/UUID -> upload receipt; (batch_id,row_number) -> import outcome | A row may reuse a canonical review while retaining an independent receipt for the requester. File hash and filename describe the upload, not a product. Counts are immutable import-event outcomes. |
| synthetic_campaigns, synthetic_campaign_members, synthetic_campaign_reviews | campaign ID/key -> campaign window and product; campaign/member and campaign/review pairs identify evidence | Separate junctions avoid repeating reviewers/reviews in campaign columns. Prior campaign is a self-referencing FK. Synthetic classification is checked and kept separate from real evaluation. |
| graph_sync_jobs, inductive_inference_jobs, inductive_prediction_evidence, audit_logs | Job IDs -> execution/lease state; prediction evidence ID and prediction FK -> evidence hashes; audit ID -> event snapshot | Operational execution, immutable evidence and historical events have distinct keys. Before/after JSON records a historical event rather than a current copy of another entity. |

The core identity and association relations follow 1NF (one typed value per column and explicit junctions), 2NF (junction attributes depend on the whole composite key), and 3NF (descriptive attributes depend on their entity key rather than another non-key description). Example decomposition: Reviews(review_id, reviewer_id, product_id, ...) + Reviewers(reviewer_id, source_system, external_reviewer_key) + Products(product_id, source_system, external_product_key, display_name).

## Explicit physical design tradeoffs

The execution schema stores provenance classifications in models, runs and jobs for composite foreign-key enforcement, and caches event counts in execution records. Some classifications are functionally derivable from linked versions; therefore it would be inaccurate to assert strict 3NF for every stored operational attribute. These are explicit integrity/performance redundancies, not additional independent business facts. Composite FKs prevent disagreeing model/run/job provenance; CHECKs validate count bounds and workflow vocabularies. Aggregate views derive reporting totals without extra summary tables.

A strictly normalized projection of an execution record obtains provenance through the model join and omits duplicated classification fields. Removing the stored columns would require replacing composite integrity constraints and changing verified serving contracts. This submission preserves those tested contracts and discloses the exception for faculty review rather than silently weakening provenance or claiming an unqualified normalization proof.

## Constraints and indexes

Each base table has a primary key. The generated schema includes 37 foreign-key columns, source-key uniqueness, rating and score ranges, checked role/source vocabularies, non-null identities, default timestamps, model verification requirements and exclusive job scope. PostgreSQL tests execute invalid rating and missing-product inserts and confirm constraint rejection. Common access paths use indexed review product/time and author/time, batch owner/date/state, prediction run/review, and feedback owner/status/date.

See `schema-postgresql.sql` for executable migration DDL, `DATA_DICTIONARY.md` for all fields, and `backend/tests/test_postgres_features.py` for executed integrity, trigger, procedure and rollback checks.
