# Current relational schema and data dictionary

This generated dictionary describes all 23 SQLAlchemy application tables. `alembic_version` is migration bookkeeping, not a domain entity. Views are derived relations, not additional base tables.

## audit_logs

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `audit_log_id` | BIGINT | No | PK |
| `actor_user_id` | BIGINT | Yes | FK users.user_id |
| `action` | VARCHAR(100) | No | - |
| `entity_type` | VARCHAR(100) | No | - |
| `entity_key` | VARCHAR(200) | No | - |
| `before_data` | JSONB | Yes | - |
| `after_data` | JSONB | Yes | - |
| `request_id` | UUID | Yes | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:

Indexes:

## batch_analyses

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `batch_analysis_id` | BIGINT | No | PK |
| `batch_key` | UUID | No | - |
| `requested_by_user_id` | BIGINT | Yes | FK users.user_id |
| `source_system` | VARCHAR(100) | No | - |
| `source_filename` | VARCHAR(255) | Yes | - |
| `historic_graph_snapshot_id` | BIGINT | Yes | FK graph_snapshots.graph_snapshot_id |
| `inference_run_id` | BIGINT | Yes | FK inference_runs.inference_run_id |
| `upload_sha256` | VARCHAR(64) | No | - |
| `row_count` | INTEGER | No | - |
| `accepted_count` | INTEGER | No | - |
| `rejected_count` | INTEGER | No | - |
| `status` | VARCHAR(30) | No | - |
| `blocking_reasons` | JSONB | No | default '[]' |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE batch_key
- CHECK row_count >= 0 AND accepted_count >= 0 AND rejected_count >= 0 AND row_count = accepted_count + rejected_count
- UNIQUE inference_run_id
- CHECK status IN ('blocked','queued','running','completed','partial','failed','validation_failed')

Indexes:
- ix_batch_analyses_created: created_at

## batch_analysis_rows

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `batch_analysis_row_id` | BIGINT | No | PK |
| `batch_analysis_id` | BIGINT | No | FK batch_analyses.batch_analysis_id |
| `row_number` | INTEGER | No | - |
| `uploaded_review_key` | VARCHAR(255) | Yes | - |
| `row_state` | VARCHAR(20) | No | - |
| `review_id` | BIGINT | Yes | FK reviews.review_id |
| `validation_errors` | JSONB | No | default '[]' |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- CHECK (row_state = 'accepted' AND review_id IS NOT NULL) OR (row_state = 'rejected' AND review_id IS NULL)
- UNIQUE batch_analysis_id, row_number
- CHECK row_state IN ('accepted','rejected')

Indexes:
- ix_batch_analysis_rows_state: batch_analysis_id, row_state, row_number

## fraud_predictions

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `fraud_prediction_id` | BIGINT | No | PK |
| `inference_run_id` | BIGINT | No | FK inference_runs.inference_run_id |
| `review_id` | BIGINT | No | FK reviews.review_id |
| `risk_score` | NUMERIC(9, 8) | No | - |
| `predicted_label` | SMALLINT | No | - |
| `attention_weights` | JSONB | Yes | - |
| `graph_status` | VARCHAR(30) | No | default not_requested |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE inference_run_id, review_id
- CHECK predicted_label IN (0,1)
- CHECK risk_score BETWEEN 0 AND 1

Indexes:
- ix_predictions_review_created: review_id, created_at

## graph_snapshot_reviews

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `graph_snapshot_id` | BIGINT | No | PK; FK graph_snapshots.graph_snapshot_id |
| `review_id` | BIGINT | No | PK; FK reviews.review_id |
| `split` | VARCHAR(20) | No | - |

Constraints:
- CHECK split IN ('train','validation','test')

Indexes:
- ix_snapshot_review_split: graph_snapshot_id, split, review_id

## graph_snapshots

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `graph_snapshot_id` | BIGINT | No | PK |
| `snapshot_key` | VARCHAR(160) | No | - |
| `dataset_name` | VARCHAR(200) | No | - |
| `dataset_sha256` | VARCHAR(64) | No | - |
| `artifact_uri` | TEXT | No | - |
| `artifact_sha256` | VARCHAR(64) | No | - |
| `graph_builder_version` | VARCHAR(160) | No | - |
| `relation_schema_version` | VARCHAR(120) | No | - |
| `split_protocol_key` | VARCHAR(160) | No | - |
| `node_count` | BIGINT | No | - |
| `edge_counts` | JSONB | No | default '{}' |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `storage_status` | VARCHAR(30) | No | default available |
| `batch_context_permitted` | BOOLEAN | No | default false |
| `context_scope_key` | VARCHAR(160) | Yes | - |
| `provenance` | VARCHAR(30) | No | default real |

Constraints:
- CHECK NOT batch_context_permitted OR (context_scope_key IS NOT NULL AND length(trim(context_scope_key)) > 0)
- UNIQUE artifact_sha256
- CHECK length(artifact_sha256) = 64 AND lower(artifact_sha256) = artifact_sha256
- CHECK storage_status IN ('available','archived','missing')
- CHECK length(dataset_sha256) = 64 AND lower(dataset_sha256) = dataset_sha256
- CHECK provenance IN ('real','synthetic_demo')
- UNIQUE snapshot_key
- CHECK node_count >= 0

Indexes:

## graph_sync_jobs

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `graph_sync_job_id` | BIGINT | No | PK |
| `operation` | VARCHAR(40) | No | - |
| `review_id` | BIGINT | Yes | FK reviews.review_id |
| `graph_snapshot_id` | BIGINT | Yes | FK graph_snapshots.graph_snapshot_id |
| `requested_by_user_id` | BIGINT | Yes | FK users.user_id |
| `source_event_key` | VARCHAR(200) | Yes | - |
| `idempotency_key` | VARCHAR(200) | Yes | - |
| `status` | VARCHAR(30) | No | default queued |
| `attempt_count` | INTEGER | No | default 0 |
| `max_attempts` | INTEGER | No | default 5 |
| `next_attempt_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `started_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `completed_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `last_error_code` | VARCHAR(100) | Yes | - |
| `last_error` | TEXT | Yes | - |
| `updated_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- CHECK status IN ('queued','running','succeeded','retry_wait','failed','cancelled')
- CHECK max_attempts > 0
- UNIQUE requested_by_user_id, idempotency_key
- CHECK (operation IN ('review_upsert','review_delete') AND review_id IS NOT NULL AND graph_snapshot_id IS NULL) OR (operation = 'snapshot_rebuild' AND review_id IS NULL AND graph_snapshot_id IS NOT NULL)
- UNIQUE source_event_key
- CHECK idempotency_key IS NULL OR requested_by_user_id IS NOT NULL
- CHECK attempt_count >= 0

Indexes:
- ix_graph_jobs_due: status, next_attempt_at

## inductive_inference_jobs

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `job_id` | BIGINT | No | PK |
| `inference_run_id` | BIGINT | No | FK inference_runs.inference_run_id |
| `status` | VARCHAR(30) | No | default queued |
| `worker_id` | VARCHAR(160) | Yes | - |
| `lease_token` | VARCHAR(160) | Yes | - |
| `lease_expires_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `attempt_count` | INTEGER | No | default 0 |
| `max_attempts` | INTEGER | No | default 5 |
| `priority` | INTEGER | No | default 100 |
| `next_attempt_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `started_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `completed_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `last_error_code` | VARCHAR(100) | Yes | - |
| `last_error` | TEXT | Yes | - |
| `provenance` | VARCHAR(30) | No | FK inference_runs.provenance; default real |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `updated_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- CHECK status IN ('queued','running','succeeded','retry_wait','failed','cancelled')
- CHECK attempt_count >= 0
- CHECK max_attempts > 0
- CHECK provenance IN ('real','synthetic_demo')
- UNIQUE inference_run_id
- UNIQUE inference_run_id

Indexes:
- ix_inductive_jobs_due: status, next_attempt_at
- ix_inductive_jobs_lease: status, lease_expires_at

## inductive_prediction_evidence

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `evidence_id` | BIGINT | No | PK |
| `fraud_prediction_id` | BIGINT | No | FK fraud_predictions.fraud_prediction_id |
| `graph_snapshot_id` | BIGINT | No | FK graph_snapshots.graph_snapshot_id |
| `relation_schema_version` | VARCHAR(120) | No | - |
| `context_cutoff_at` | TIMESTAMP WITH TIME ZONE | No | - |
| `neighbor_counts` | JSONB | No | default '{}' |
| `historic_review_ids` | JSONB | No | default '[]' |
| `stitched_graph_sha256` | VARCHAR(64) | No | - |
| `input_feature_sha256` | VARCHAR(64) | No | - |
| `embedding_sha256` | VARCHAR(64) | No | - |
| `bundle_manifest_sha256` | VARCHAR(64) | No | - |
| `provenance` | VARCHAR(30) | No | default real |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE fraud_prediction_id
- CHECK provenance IN ('real','synthetic_demo')
- CHECK length(stitched_graph_sha256) = 64 AND lower(stitched_graph_sha256) = stitched_graph_sha256
- CHECK length(bundle_manifest_sha256) = 64 AND lower(bundle_manifest_sha256) = bundle_manifest_sha256
- UNIQUE fraud_prediction_id
- CHECK length(embedding_sha256) = 64 AND lower(embedding_sha256) = embedding_sha256
- CHECK length(input_feature_sha256) = 64 AND lower(input_feature_sha256) = input_feature_sha256

Indexes:
- ix_inductive_evidence_cutoff: context_cutoff_at
- ix_inductive_evidence_snapshot: graph_snapshot_id

## inference_runs

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `inference_run_id` | BIGINT | No | PK |
| `run_key` | UUID | No | - |
| `model_version_id` | BIGINT | No | FK model_versions.model_version_id; FK model_versions.model_version_id |
| `provenance` | VARCHAR(30) | No | FK model_versions.provenance; default real |
| `graph_snapshot_id` | BIGINT | No | FK graph_snapshots.graph_snapshot_id |
| `requested_by_user_id` | BIGINT | Yes | FK users.user_id |
| `idempotency_key` | VARCHAR(200) | Yes | - |
| `threshold` | NUMERIC(8, 7) | No | - |
| `status` | VARCHAR(30) | No | default queued |
| `requested_count` | INTEGER | No | - |
| `completed_count` | INTEGER | No | default 0 |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `completed_at` | TIMESTAMP WITH TIME ZONE | Yes | - |

Constraints:
- UNIQUE inference_run_id, provenance
- CHECK threshold BETWEEN 0 AND 1
- CHECK requested_count > 0 AND completed_count >= 0 AND completed_count <= requested_count
- CHECK status IN ('queued','running','completed','failed','cancelled')
- CHECK idempotency_key IS NULL OR requested_by_user_id IS NOT NULL
- UNIQUE requested_by_user_id, idempotency_key
- UNIQUE run_key

Indexes:

## model_versions

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `model_version_id` | BIGINT | No | PK |
| `version_key` | VARCHAR(160) | No | - |
| `model_name` | VARCHAR(100) | No | - |
| `architecture_version` | VARCHAR(100) | No | - |
| `architecture_config` | JSONB | No | default '{}' |
| `config_sha256` | VARCHAR(64) | No | - |
| `checkpoint_uri` | TEXT | Yes | - |
| `checkpoint_sha256` | VARCHAR(64) | Yes | - |
| `preprocessing_version_id` | BIGINT | No | FK preprocessing_versions.preprocessing_version_id |
| `input_contract_version` | VARCHAR(100) | No | - |
| `supported_inference_mode` | VARCHAR(50) | No | default known_node_only |
| `recommended_threshold` | NUMERIC(8, 7) | Yes | - |
| `threshold_source` | TEXT | Yes | - |
| `lifecycle_status` | VARCHAR(30) | No | default unavailable |
| `provenance` | VARCHAR(30) | No | default real |
| `verification_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- CHECK provenance = 'real' OR lifecycle_status <> 'verified'
- UNIQUE version_key
- CHECK recommended_threshold IS NULL OR recommended_threshold BETWEEN 0 AND 1
- UNIQUE checkpoint_sha256
- CHECK lifecycle_status IN ('unavailable','registered','verified','retired')
- CHECK checkpoint_sha256 IS NULL OR (length(checkpoint_sha256) = 64 AND lower(checkpoint_sha256) = checkpoint_sha256)
- CHECK provenance IN ('real','synthetic_demo')
- UNIQUE model_version_id, provenance
- CHECK supported_inference_mode IN ('known_node_only', 'inductive_batch_v1')
- CHECK length(config_sha256) = 64 AND lower(config_sha256) = config_sha256
- CHECK lifecycle_status <> 'verified' OR (checkpoint_uri IS NOT NULL AND checkpoint_sha256 IS NOT NULL AND recommended_threshold IS NOT NULL AND threshold_source IS NOT NULL AND verification_at IS NOT NULL)

Indexes:
- ix_model_versions_model_name: model_name
- ix_model_versions_preprocessing_version_id: preprocessing_version_id

## preprocessing_versions

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `preprocessing_version_id` | BIGINT | No | PK |
| `version_key` | VARCHAR(160) | No | - |
| `preprocessing_sha256` | VARCHAR(64) | No | - |
| `preprocessing_config` | JSONB | No | default '{}' |
| `code_revision` | VARCHAR(160) | No | - |
| `lifecycle_status` | VARCHAR(30) | No | default registered |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `verified_at` | TIMESTAMP WITH TIME ZONE | Yes | - |

Constraints:
- UNIQUE preprocessing_sha256
- CHECK lifecycle_status IN ('registered','verified','retired','unavailable')
- UNIQUE version_key
- CHECK length(preprocessing_sha256) = 64 AND lower(preprocessing_sha256) = preprocessing_sha256

Indexes:

## products

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `product_id` | BIGINT | No | PK |
| `source_system` | VARCHAR(100) | No | - |
| `external_product_key` | VARCHAR(255) | No | - |
| `display_name` | VARCHAR(500) | Yes | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE source_system, external_product_key

Indexes:

## review_feedback

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `feedback_id` | BIGINT | No | PK |
| `review_id` | BIGINT | No | FK reviews.review_id |
| `submitted_by_user_id` | BIGINT | Yes | FK users.user_id |
| `feedback_type` | VARCHAR(40) | No | - |
| `ground_truth_label` | SMALLINT | Yes | - |
| `comment` | TEXT | Yes | - |
| `idempotency_key` | VARCHAR(200) | Yes | - |
| `status` | VARCHAR(30) | No | default submitted |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- CHECK feedback_type IN ('label_correction','review_quality','other')
- CHECK ground_truth_label IS NULL OR ground_truth_label IN (0,1)
- CHECK idempotency_key IS NULL OR submitted_by_user_id IS NOT NULL
- UNIQUE submitted_by_user_id, idempotency_key
- CHECK status IN ('submitted','triaged','resolved','rejected')

Indexes:
- ix_feedback_owner_status: submitted_by_user_id, status, created_at

## review_variants

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `review_variant_id` | BIGINT | No | PK |
| `review_id` | BIGINT | No | FK reviews.review_id |
| `variant_key` | VARCHAR(160) | No | - |
| `variant_type` | VARCHAR(80) | No | - |
| `variant_text` | TEXT | Yes | - |
| `review_metadata` | JSONB | No | default '{}' |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE review_id, variant_key

Indexes:

## reviewers

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `reviewer_id` | BIGINT | No | PK |
| `source_system` | VARCHAR(100) | No | - |
| `external_reviewer_key` | VARCHAR(255) | No | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE source_system, external_reviewer_key

Indexes:

## reviews

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `review_id` | BIGINT | No | PK |
| `source_system` | VARCHAR(100) | Yes | - |
| `source_review_key` | VARCHAR(255) | Yes | - |
| `reviewer_id` | BIGINT | Yes | FK reviewers.reviewer_id |
| `product_id` | BIGINT | Yes | FK products.product_id |
| `submitted_by_user_id` | BIGINT | Yes | FK users.user_id |
| `rating` | SMALLINT | Yes | - |
| `reviewed_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `review_text` | TEXT | Yes | - |
| `ground_truth_label` | SMALLINT | Yes | - |
| `label_source` | VARCHAR(255) | Yes | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `updated_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- CHECK rating IS NULL OR rating BETWEEN 1 AND 5
- CHECK ground_truth_label IS NULL OR ground_truth_label IN (0, 1)
- CHECK (source_system IS NULL) = (source_review_key IS NULL)

Indexes:
- ix_reviews_product_date: product_id, reviewed_at
- ix_reviews_product_id: product_id
- ix_reviews_reviewer_date: reviewer_id, reviewed_at
- ix_reviews_reviewer_id: reviewer_id
- ix_reviews_submitted_by_user_id: submitted_by_user_id
- uq_reviews_source_pair: source_system, source_review_key (unique)

## roles

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `role_id` | BIGINT | No | PK |
| `role_key` | VARCHAR(40) | No | - |
| `display_name` | VARCHAR(120) | No | - |
| `description` | TEXT | Yes | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE role_key

Indexes:

## session_tokens

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `session_token_id` | UUID | No | PK |
| `user_id` | BIGINT | No | FK users.user_id |
| `access_jti_hash` | VARCHAR(64) | No | - |
| `refresh_token_hash` | VARCHAR(64) | No | - |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `last_used_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `access_expires_at` | TIMESTAMP WITH TIME ZONE | No | - |
| `refresh_expires_at` | TIMESTAMP WITH TIME ZONE | No | - |
| `revoked_at` | TIMESTAMP WITH TIME ZONE | Yes | - |
| `replaced_by_session_id` | UUID | Yes | FK session_tokens.session_token_id |

Constraints:
- UNIQUE refresh_token_hash
- UNIQUE access_jti_hash
- CHECK access_expires_at > created_at AND access_expires_at <= refresh_expires_at
- CHECK refresh_expires_at > created_at

Indexes:
- ix_session_tokens_active: user_id, refresh_expires_at
- ix_session_tokens_user_id: user_id

## synthetic_campaign_members

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `synthetic_campaign_member_id` | BIGINT | No | PK |
| `synthetic_campaign_id` | BIGINT | No | FK synthetic_campaigns.synthetic_campaign_id |
| `reviewer_id` | BIGINT | No | FK reviewers.reviewer_id |
| `membership_type` | VARCHAR(30) | No | - |
| `provenance` | VARCHAR(30) | No | default synthetic_demo |

Constraints:
- CHECK provenance = 'synthetic_demo'
- CHECK membership_type IN ('attack_participant','prior_participant')
- UNIQUE synthetic_campaign_id, reviewer_id

Indexes:
- ix_campaign_members_reviewer: reviewer_id, synthetic_campaign_id

## synthetic_campaign_reviews

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `synthetic_campaign_review_id` | BIGINT | No | PK |
| `synthetic_campaign_id` | BIGINT | No | FK synthetic_campaigns.synthetic_campaign_id |
| `review_id` | BIGINT | No | FK reviews.review_id |
| `campaign_period` | VARCHAR(20) | No | - |
| `evidence_note` | TEXT | No | - |
| `provenance` | VARCHAR(30) | No | default synthetic_demo |

Constraints:
- CHECK campaign_period IN ('attack','prior')
- CHECK provenance = 'synthetic_demo'
- UNIQUE synthetic_campaign_id, review_id

Indexes:
- ix_campaign_reviews_period: synthetic_campaign_id, campaign_period, review_id

## synthetic_campaigns

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `synthetic_campaign_id` | BIGINT | No | PK |
| `campaign_key` | VARCHAR(160) | No | - |
| `campaign_name` | VARCHAR(200) | No | - |
| `product_id` | BIGINT | No | FK products.product_id |
| `prior_campaign_id` | BIGINT | Yes | FK synthetic_campaigns.synthetic_campaign_id |
| `prior_start_at` | TIMESTAMP WITH TIME ZONE | No | - |
| `prior_end_at` | TIMESTAMP WITH TIME ZONE | No | - |
| `attack_start_at` | TIMESTAMP WITH TIME ZONE | No | - |
| `attack_end_at` | TIMESTAMP WITH TIME ZONE | No | - |
| `description` | TEXT | No | - |
| `provenance` | VARCHAR(30) | No | default synthetic_demo |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |

Constraints:
- UNIQUE campaign_key
- CHECK prior_start_at < prior_end_at
- CHECK prior_end_at <= attack_start_at
- CHECK provenance = 'synthetic_demo'
- CHECK attack_start_at < attack_end_at

Indexes:
- ix_campaign_product_attack: product_id, attack_start_at, attack_end_at

## users

| Column | PostgreSQL type | Null | Key or default |
|---|---|---|---|
| `user_id` | BIGINT | No | PK |
| `role_id` | BIGINT | No | FK roles.role_id |
| `email` | VARCHAR(320) | No | - |
| `email_normalized` | VARCHAR(320) | No | - |
| `username` | VARCHAR(80) | Yes | - |
| `password_hash` | VARCHAR(512) | No | - |
| `is_active` | BOOLEAN | No | default true |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `updated_at` | TIMESTAMP WITH TIME ZONE | No | default now() |
| `last_login_at` | TIMESTAMP WITH TIME ZONE | Yes | - |

Constraints:
- UNIQUE email_normalized
- CHECK email_normalized = lower(trim(email))
- UNIQUE username

Indexes:
- ix_users_role_id: role_id
