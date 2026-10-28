BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial_schema

CREATE TABLE graph_snapshots (
    graph_snapshot_id BIGSERIAL NOT NULL, 
    snapshot_key VARCHAR(160) NOT NULL, 
    dataset_name VARCHAR(200) NOT NULL, 
    dataset_sha256 VARCHAR(64) NOT NULL, 
    artifact_uri TEXT NOT NULL, 
    artifact_sha256 VARCHAR(64) NOT NULL, 
    graph_builder_version VARCHAR(160) NOT NULL, 
    relation_schema_version VARCHAR(120) NOT NULL, 
    split_protocol_key VARCHAR(160) NOT NULL, 
    node_count BIGINT NOT NULL, 
    edge_counts JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    storage_status VARCHAR(30) DEFAULT 'available' NOT NULL, 
    PRIMARY KEY (graph_snapshot_id), 
    CONSTRAINT ck_graph_snapshot_storage CHECK (storage_status IN ('available','archived','missing')), 
    CONSTRAINT ck_graph_artifact_sha256 CHECK (length(artifact_sha256) = 64 AND lower(artifact_sha256) = artifact_sha256), 
    CONSTRAINT ck_graph_dataset_sha256 CHECK (length(dataset_sha256) = 64 AND lower(dataset_sha256) = dataset_sha256), 
    CONSTRAINT ck_graph_snapshot_node_count CHECK (node_count >= 0), 
    UNIQUE (artifact_sha256), 
    UNIQUE (snapshot_key)
);

CREATE TABLE preprocessing_versions (
    preprocessing_version_id BIGSERIAL NOT NULL, 
    version_key VARCHAR(160) NOT NULL, 
    preprocessing_sha256 VARCHAR(64) NOT NULL, 
    preprocessing_config JSONB DEFAULT '{}' NOT NULL, 
    code_revision VARCHAR(160) NOT NULL, 
    lifecycle_status VARCHAR(30) DEFAULT 'registered' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    verified_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (preprocessing_version_id), 
    CONSTRAINT ck_preprocessing_status CHECK (lifecycle_status IN ('registered','verified','retired','unavailable')), 
    CONSTRAINT ck_preprocessing_sha256 CHECK (length(preprocessing_sha256) = 64 AND lower(preprocessing_sha256) = preprocessing_sha256), 
    UNIQUE (preprocessing_sha256), 
    UNIQUE (version_key)
);

CREATE TABLE products (
    product_id BIGSERIAL NOT NULL, 
    source_system VARCHAR(100) NOT NULL, 
    external_product_key VARCHAR(255) NOT NULL, 
    display_name VARCHAR(500), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (product_id), 
    CONSTRAINT uq_products_source_key UNIQUE (source_system, external_product_key)
);

CREATE TABLE reviewers (
    reviewer_id BIGSERIAL NOT NULL, 
    source_system VARCHAR(100) NOT NULL, 
    external_reviewer_key VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (reviewer_id), 
    CONSTRAINT uq_reviewers_source_key UNIQUE (source_system, external_reviewer_key)
);

CREATE TABLE roles (
    role_id BIGSERIAL NOT NULL, 
    role_key VARCHAR(40) NOT NULL, 
    display_name VARCHAR(120) NOT NULL, 
    description TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (role_id), 
    UNIQUE (role_key)
);

CREATE TABLE model_versions (
    model_version_id BIGSERIAL NOT NULL, 
    version_key VARCHAR(160) NOT NULL, 
    model_name VARCHAR(100) NOT NULL, 
    architecture_version VARCHAR(100) NOT NULL, 
    architecture_config JSONB DEFAULT '{}' NOT NULL, 
    config_sha256 VARCHAR(64) NOT NULL, 
    checkpoint_uri TEXT, 
    checkpoint_sha256 VARCHAR(64), 
    preprocessing_version_id BIGINT NOT NULL, 
    input_contract_version VARCHAR(100) NOT NULL, 
    supported_inference_mode VARCHAR(50) DEFAULT 'known_node_only' NOT NULL, 
    recommended_threshold NUMERIC(8, 7), 
    threshold_source TEXT, 
    lifecycle_status VARCHAR(30) DEFAULT 'unavailable' NOT NULL, 
    verification_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (model_version_id), 
    CONSTRAINT ck_model_verified_requirements CHECK (lifecycle_status <> 'verified' OR (checkpoint_uri IS NOT NULL AND checkpoint_sha256 IS NOT NULL AND recommended_threshold IS NOT NULL AND threshold_source IS NOT NULL AND verification_at IS NOT NULL)), 
    CONSTRAINT ck_model_lifecycle CHECK (lifecycle_status IN ('unavailable','registered','verified','retired')), 
    CONSTRAINT ck_model_inference_mode CHECK (supported_inference_mode IN ('known_node_only')), 
    CONSTRAINT ck_model_checkpoint_sha256 CHECK (checkpoint_sha256 IS NULL OR (length(checkpoint_sha256) = 64 AND lower(checkpoint_sha256) = checkpoint_sha256)), 
    CONSTRAINT ck_model_config_sha256 CHECK (length(config_sha256) = 64 AND lower(config_sha256) = config_sha256), 
    CONSTRAINT ck_model_threshold CHECK (recommended_threshold IS NULL OR recommended_threshold BETWEEN 0 AND 1), 
    FOREIGN KEY(preprocessing_version_id) REFERENCES preprocessing_versions (preprocessing_version_id) ON DELETE RESTRICT, 
    UNIQUE (checkpoint_sha256), 
    UNIQUE (version_key)
);

CREATE INDEX ix_model_versions_model_name ON model_versions (model_name);

CREATE INDEX ix_model_versions_preprocessing_version_id ON model_versions (preprocessing_version_id);

CREATE TABLE users (
    user_id BIGSERIAL NOT NULL, 
    role_id BIGINT NOT NULL, 
    email VARCHAR(320) NOT NULL, 
    email_normalized VARCHAR(320) NOT NULL, 
    username VARCHAR(80), 
    password_hash VARCHAR(512) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (user_id), 
    CONSTRAINT ck_users_email_normalized CHECK (email_normalized = lower(trim(email))), 
    FOREIGN KEY(role_id) REFERENCES roles (role_id) ON DELETE RESTRICT, 
    UNIQUE (email_normalized), 
    UNIQUE (username)
);

CREATE INDEX ix_users_role_id ON users (role_id);

CREATE TABLE audit_logs (
    audit_log_id BIGSERIAL NOT NULL, 
    actor_user_id BIGINT, 
    action VARCHAR(100) NOT NULL, 
    entity_type VARCHAR(100) NOT NULL, 
    entity_key VARCHAR(200) NOT NULL, 
    before_data JSONB, 
    after_data JSONB, 
    request_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (audit_log_id), 
    FOREIGN KEY(actor_user_id) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE TABLE inference_runs (
    inference_run_id BIGSERIAL NOT NULL, 
    run_key UUID NOT NULL, 
    model_version_id BIGINT NOT NULL, 
    graph_snapshot_id BIGINT NOT NULL, 
    requested_by_user_id BIGINT, 
    idempotency_key VARCHAR(200), 
    threshold NUMERIC(8, 7) NOT NULL, 
    status VARCHAR(30) DEFAULT 'queued' NOT NULL, 
    requested_count INTEGER NOT NULL, 
    completed_count INTEGER DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (inference_run_id), 
    CONSTRAINT ck_inference_status CHECK (status IN ('queued','running','completed','failed','cancelled')), 
    CONSTRAINT ck_inference_idempotency_owner CHECK (idempotency_key IS NULL OR requested_by_user_id IS NOT NULL), 
    CONSTRAINT ck_inference_counts CHECK (requested_count > 0 AND completed_count >= 0 AND completed_count <= requested_count), 
    CONSTRAINT ck_inference_threshold CHECK (threshold BETWEEN 0 AND 1), 
    FOREIGN KEY(graph_snapshot_id) REFERENCES graph_snapshots (graph_snapshot_id) ON DELETE RESTRICT, 
    FOREIGN KEY(model_version_id) REFERENCES model_versions (model_version_id) ON DELETE RESTRICT, 
    FOREIGN KEY(requested_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL, 
    CONSTRAINT uq_inference_user_idempotency UNIQUE (requested_by_user_id, idempotency_key), 
    UNIQUE (run_key)
);

CREATE TABLE reviews (
    review_id BIGSERIAL NOT NULL, 
    source_system VARCHAR(100), 
    source_review_key VARCHAR(255), 
    reviewer_id BIGINT, 
    product_id BIGINT, 
    submitted_by_user_id BIGINT, 
    rating SMALLINT, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    review_text TEXT, 
    ground_truth_label SMALLINT, 
    label_source VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (review_id), 
    CONSTRAINT ck_reviews_source_pair CHECK ((source_system IS NULL) = (source_review_key IS NULL)), 
    CONSTRAINT ck_reviews_ground_truth CHECK (ground_truth_label IS NULL OR ground_truth_label IN (0, 1)), 
    CONSTRAINT ck_reviews_rating CHECK (rating IS NULL OR rating BETWEEN 1 AND 5), 
    FOREIGN KEY(product_id) REFERENCES products (product_id) ON DELETE SET NULL, 
    FOREIGN KEY(reviewer_id) REFERENCES reviewers (reviewer_id) ON DELETE SET NULL, 
    FOREIGN KEY(submitted_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE INDEX ix_reviews_product_date ON reviews (product_id, reviewed_at);

CREATE INDEX ix_reviews_product_id ON reviews (product_id);

CREATE INDEX ix_reviews_reviewer_date ON reviews (reviewer_id, reviewed_at);

CREATE INDEX ix_reviews_reviewer_id ON reviews (reviewer_id);

CREATE INDEX ix_reviews_submitted_by_user_id ON reviews (submitted_by_user_id);

CREATE UNIQUE INDEX uq_reviews_source_pair ON reviews (source_system, source_review_key) WHERE source_system IS NOT NULL;

CREATE TABLE session_tokens (
    session_token_id UUID NOT NULL, 
    user_id BIGINT NOT NULL, 
    access_jti_hash VARCHAR(64) NOT NULL, 
    refresh_token_hash VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    access_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    refresh_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    replaced_by_session_id UUID, 
    PRIMARY KEY (session_token_id), 
    CONSTRAINT ck_session_access_expiry CHECK (access_expires_at > created_at AND access_expires_at <= refresh_expires_at), 
    CONSTRAINT ck_session_refresh_expiry CHECK (refresh_expires_at > created_at), 
    FOREIGN KEY(replaced_by_session_id) REFERENCES session_tokens (session_token_id) ON DELETE SET NULL, 
    FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE CASCADE, 
    UNIQUE (access_jti_hash), 
    UNIQUE (refresh_token_hash)
);

CREATE INDEX ix_session_tokens_active ON session_tokens (user_id, refresh_expires_at) WHERE revoked_at IS NULL;

CREATE INDEX ix_session_tokens_user_id ON session_tokens (user_id);

CREATE TABLE fraud_predictions (
    fraud_prediction_id BIGSERIAL NOT NULL, 
    inference_run_id BIGINT NOT NULL, 
    review_id BIGINT NOT NULL, 
    risk_score NUMERIC(9, 8) NOT NULL, 
    predicted_label SMALLINT NOT NULL, 
    attention_weights JSONB, 
    graph_status VARCHAR(30) DEFAULT 'not_requested' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (fraud_prediction_id), 
    CONSTRAINT ck_prediction_label CHECK (predicted_label IN (0,1)), 
    CONSTRAINT ck_prediction_score CHECK (risk_score BETWEEN 0 AND 1), 
    FOREIGN KEY(inference_run_id) REFERENCES inference_runs (inference_run_id) ON DELETE RESTRICT, 
    FOREIGN KEY(review_id) REFERENCES reviews (review_id) ON DELETE RESTRICT, 
    CONSTRAINT uq_predictions_run_review UNIQUE (inference_run_id, review_id)
);

CREATE INDEX ix_predictions_review_created ON fraud_predictions (review_id, created_at);

CREATE TABLE graph_snapshot_reviews (
    graph_snapshot_id BIGINT NOT NULL, 
    review_id BIGINT NOT NULL, 
    split VARCHAR(20) NOT NULL, 
    PRIMARY KEY (graph_snapshot_id, review_id), 
    CONSTRAINT ck_snapshot_review_split CHECK (split IN ('train','validation','test')), 
    FOREIGN KEY(graph_snapshot_id) REFERENCES graph_snapshots (graph_snapshot_id) ON DELETE CASCADE, 
    FOREIGN KEY(review_id) REFERENCES reviews (review_id) ON DELETE RESTRICT
);

CREATE INDEX ix_snapshot_review_split ON graph_snapshot_reviews (graph_snapshot_id, split, review_id);

CREATE TABLE graph_sync_jobs (
    graph_sync_job_id BIGSERIAL NOT NULL, 
    operation VARCHAR(40) NOT NULL, 
    review_id BIGINT, 
    graph_snapshot_id BIGINT, 
    requested_by_user_id BIGINT, 
    source_event_key VARCHAR(200), 
    idempotency_key VARCHAR(200), 
    status VARCHAR(30) DEFAULT 'queued' NOT NULL, 
    attempt_count INTEGER DEFAULT '0' NOT NULL, 
    max_attempts INTEGER DEFAULT '5' NOT NULL, 
    next_attempt_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    last_error_code VARCHAR(100), 
    last_error TEXT, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (graph_sync_job_id), 
    CONSTRAINT ck_graph_job_scope CHECK ((operation IN ('review_upsert','review_delete') AND review_id IS NOT NULL AND graph_snapshot_id IS NULL) OR (operation = 'snapshot_rebuild' AND review_id IS NULL AND graph_snapshot_id IS NOT NULL)), 
    CONSTRAINT ck_graph_job_status CHECK (status IN ('queued','running','succeeded','retry_wait','failed','cancelled')), 
    CONSTRAINT ck_graph_job_attempt_count CHECK (attempt_count >= 0), 
    CONSTRAINT ck_graph_job_idempotency_owner CHECK (idempotency_key IS NULL OR requested_by_user_id IS NOT NULL), 
    CONSTRAINT ck_graph_job_max_attempts CHECK (max_attempts > 0), 
    FOREIGN KEY(graph_snapshot_id) REFERENCES graph_snapshots (graph_snapshot_id) ON DELETE RESTRICT, 
    FOREIGN KEY(requested_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL, 
    FOREIGN KEY(review_id) REFERENCES reviews (review_id) ON DELETE RESTRICT, 
    CONSTRAINT uq_graph_job_user_idempotency UNIQUE (requested_by_user_id, idempotency_key), 
    CONSTRAINT uq_graph_job_source_event UNIQUE (source_event_key)
);

CREATE INDEX ix_graph_jobs_due ON graph_sync_jobs (status, next_attempt_at) WHERE status IN ('queued','retry_wait');

CREATE TABLE review_feedback (
    feedback_id BIGSERIAL NOT NULL, 
    review_id BIGINT NOT NULL, 
    submitted_by_user_id BIGINT, 
    feedback_type VARCHAR(40) NOT NULL, 
    ground_truth_label SMALLINT, 
    comment TEXT, 
    idempotency_key VARCHAR(200), 
    status VARCHAR(30) DEFAULT 'submitted' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (feedback_id), 
    CONSTRAINT ck_feedback_type CHECK (feedback_type IN ('label_correction','review_quality','other')), 
    CONSTRAINT ck_feedback_status CHECK (status IN ('submitted','triaged','resolved','rejected')), 
    CONSTRAINT ck_feedback_label CHECK (ground_truth_label IS NULL OR ground_truth_label IN (0,1)), 
    CONSTRAINT ck_feedback_idempotency_owner CHECK (idempotency_key IS NULL OR submitted_by_user_id IS NOT NULL), 
    FOREIGN KEY(review_id) REFERENCES reviews (review_id) ON DELETE RESTRICT, 
    FOREIGN KEY(submitted_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL, 
    CONSTRAINT uq_feedback_user_idempotency UNIQUE (submitted_by_user_id, idempotency_key)
);

CREATE TABLE review_variants (
    review_variant_id BIGSERIAL NOT NULL, 
    review_id BIGINT NOT NULL, 
    variant_key VARCHAR(160) NOT NULL, 
    variant_type VARCHAR(80) NOT NULL, 
    variant_text TEXT, 
    review_metadata JSONB DEFAULT '{}' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (review_variant_id), 
    FOREIGN KEY(review_id) REFERENCES reviews (review_id) ON DELETE CASCADE, 
    CONSTRAINT uq_review_variants_key UNIQUE (review_id, variant_key)
);

INSERT INTO alembic_version (version_num) VALUES ('0001_initial_schema') RETURNING alembic_version.version_num;

-- Running upgrade 0001_initial_schema -> 0002_batch_analyses

ALTER TABLE graph_snapshots ADD COLUMN batch_context_permitted BOOLEAN DEFAULT false NOT NULL;

CREATE TABLE batch_analyses (
    batch_analysis_id BIGSERIAL NOT NULL, 
    batch_key UUID NOT NULL, 
    requested_by_user_id BIGINT, 
    source_system VARCHAR(100) NOT NULL, 
    historic_graph_snapshot_id BIGINT, 
    inference_run_id BIGINT, 
    upload_sha256 VARCHAR(64) NOT NULL, 
    row_count INTEGER NOT NULL, 
    accepted_count INTEGER NOT NULL, 
    rejected_count INTEGER NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    blocking_reasons JSONB DEFAULT '[]' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (batch_analysis_id), 
    CONSTRAINT ck_batch_analysis_status CHECK (status IN ('blocked','queued','running','completed','partial','failed','validation_failed')), 
    CONSTRAINT ck_batch_analysis_counts CHECK (row_count >= 0 AND accepted_count >= 0 AND rejected_count >= 0 AND row_count = accepted_count + rejected_count), 
    FOREIGN KEY(requested_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL, 
    FOREIGN KEY(historic_graph_snapshot_id) REFERENCES graph_snapshots (graph_snapshot_id) ON DELETE RESTRICT, 
    FOREIGN KEY(inference_run_id) REFERENCES inference_runs (inference_run_id) ON DELETE RESTRICT, 
    UNIQUE (batch_key), 
    UNIQUE (inference_run_id)
);

CREATE INDEX ix_batch_analyses_created ON batch_analyses (created_at);

CREATE TABLE batch_analysis_rows (
    batch_analysis_row_id BIGSERIAL NOT NULL, 
    batch_analysis_id BIGINT NOT NULL, 
    row_number INTEGER NOT NULL, 
    uploaded_review_key VARCHAR(255), 
    row_state VARCHAR(20) NOT NULL, 
    review_id BIGINT, 
    validation_errors JSONB DEFAULT '[]' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (batch_analysis_row_id), 
    CONSTRAINT ck_batch_analysis_row_state CHECK (row_state IN ('accepted','rejected')), 
    CONSTRAINT ck_batch_analysis_row_review CHECK ((row_state = 'accepted' AND review_id IS NOT NULL) OR (row_state = 'rejected' AND review_id IS NULL)), 
    FOREIGN KEY(batch_analysis_id) REFERENCES batch_analyses (batch_analysis_id) ON DELETE CASCADE, 
    FOREIGN KEY(review_id) REFERENCES reviews (review_id) ON DELETE RESTRICT, 
    CONSTRAINT uq_batch_analysis_row_number UNIQUE (batch_analysis_id, row_number)
);

CREATE INDEX ix_batch_analysis_rows_state ON batch_analysis_rows (batch_analysis_id, row_state, row_number);

UPDATE alembic_version SET version_num='0002_batch_analyses' WHERE alembic_version.version_num = '0001_initial_schema';

-- Running upgrade 0002_batch_analyses -> 0003_add_provenance_tracking

ALTER TABLE model_versions ADD COLUMN provenance VARCHAR(30) DEFAULT 'real' NOT NULL;

ALTER TABLE model_versions ADD CONSTRAINT ck_mv_prov CHECK (provenance IN ('real','synthetic_demo'));

ALTER TABLE model_versions ADD CONSTRAINT ck_mv_demo_not_verified CHECK (provenance = 'real' OR lifecycle_status <> 'verified');

ALTER TABLE model_versions ADD CONSTRAINT uq_mv_id_prov UNIQUE (model_version_id, provenance);

ALTER TABLE inference_runs ADD COLUMN provenance VARCHAR(30) DEFAULT 'real' NOT NULL;

ALTER TABLE inference_runs ADD CONSTRAINT fk_run_model_prov FOREIGN KEY(model_version_id, provenance) REFERENCES model_versions (model_version_id, provenance);

UPDATE alembic_version SET version_num='0003_add_provenance_tracking' WHERE alembic_version.version_num = '0002_batch_analyses';

-- Running upgrade 0003_add_provenance_tracking -> 0004_synthetic_campaigns

ALTER TABLE graph_snapshots ADD COLUMN provenance VARCHAR(30) DEFAULT 'real' NOT NULL;

ALTER TABLE graph_snapshots ADD CONSTRAINT ck_graph_snapshot_provenance CHECK (provenance IN ('real','synthetic_demo'));

CREATE TABLE synthetic_campaigns (
    synthetic_campaign_id BIGSERIAL NOT NULL, 
    campaign_key VARCHAR(160) NOT NULL, 
    campaign_name VARCHAR(200) NOT NULL, 
    product_id BIGINT NOT NULL, 
    prior_campaign_id BIGINT, 
    prior_start_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    prior_end_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    attack_start_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    attack_end_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    description TEXT NOT NULL, 
    provenance VARCHAR(30) DEFAULT 'synthetic_demo' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (synthetic_campaign_id), 
    CONSTRAINT ck_campaign_provenance CHECK (provenance = 'synthetic_demo'), 
    CONSTRAINT ck_campaign_attack_window CHECK (attack_start_at < attack_end_at), 
    CONSTRAINT ck_campaign_prior_window CHECK (prior_start_at < prior_end_at), 
    CONSTRAINT ck_campaign_windows_order CHECK (prior_end_at <= attack_start_at), 
    FOREIGN KEY(product_id) REFERENCES products (product_id) ON DELETE RESTRICT, 
    FOREIGN KEY(prior_campaign_id) REFERENCES synthetic_campaigns (synthetic_campaign_id) ON DELETE SET NULL, 
    UNIQUE (campaign_key)
);

CREATE INDEX ix_campaign_product_attack ON synthetic_campaigns (product_id, attack_start_at, attack_end_at);

CREATE TABLE synthetic_campaign_members (
    synthetic_campaign_member_id BIGSERIAL NOT NULL, 
    synthetic_campaign_id BIGINT NOT NULL, 
    reviewer_id BIGINT NOT NULL, 
    membership_type VARCHAR(30) NOT NULL, 
    provenance VARCHAR(30) DEFAULT 'synthetic_demo' NOT NULL, 
    PRIMARY KEY (synthetic_campaign_member_id), 
    CONSTRAINT ck_campaign_member_provenance CHECK (provenance = 'synthetic_demo'), 
    CONSTRAINT ck_campaign_member_type CHECK (membership_type IN ('attack_participant','prior_participant')), 
    FOREIGN KEY(synthetic_campaign_id) REFERENCES synthetic_campaigns (synthetic_campaign_id) ON DELETE CASCADE, 
    FOREIGN KEY(reviewer_id) REFERENCES reviewers (reviewer_id) ON DELETE RESTRICT, 
    CONSTRAINT uq_campaign_member_reviewer UNIQUE (synthetic_campaign_id, reviewer_id)
);

CREATE INDEX ix_campaign_members_reviewer ON synthetic_campaign_members (reviewer_id, synthetic_campaign_id);

CREATE TABLE synthetic_campaign_reviews (
    synthetic_campaign_review_id BIGSERIAL NOT NULL, 
    synthetic_campaign_id BIGINT NOT NULL, 
    review_id BIGINT NOT NULL, 
    campaign_period VARCHAR(20) NOT NULL, 
    evidence_note TEXT NOT NULL, 
    provenance VARCHAR(30) DEFAULT 'synthetic_demo' NOT NULL, 
    PRIMARY KEY (synthetic_campaign_review_id), 
    CONSTRAINT ck_campaign_review_provenance CHECK (provenance = 'synthetic_demo'), 
    CONSTRAINT ck_campaign_review_period CHECK (campaign_period IN ('attack','prior')), 
    FOREIGN KEY(synthetic_campaign_id) REFERENCES synthetic_campaigns (synthetic_campaign_id) ON DELETE CASCADE, 
    FOREIGN KEY(review_id) REFERENCES reviews (review_id) ON DELETE RESTRICT, 
    CONSTRAINT uq_campaign_review UNIQUE (synthetic_campaign_id, review_id)
);

CREATE INDEX ix_campaign_reviews_period ON synthetic_campaign_reviews (synthetic_campaign_id, campaign_period, review_id);

UPDATE alembic_version SET version_num='0004_synthetic_campaigns' WHERE alembic_version.version_num = '0003_add_provenance_tracking';

-- Running upgrade 0004_synthetic_campaigns -> 0005_inductive_batch_scoring

ALTER TABLE graph_snapshots ADD COLUMN context_scope_key VARCHAR(160);

ALTER TABLE graph_snapshots ADD CONSTRAINT ck_snapshot_context_scope CHECK (NOT batch_context_permitted OR (context_scope_key IS NOT NULL AND length(trim(context_scope_key)) > 0));

ALTER TABLE model_versions DROP CONSTRAINT ck_model_inference_mode;

ALTER TABLE model_versions ADD CONSTRAINT ck_model_inference_mode CHECK (supported_inference_mode IN ('known_node_only', 'inductive_batch_v1'));

ALTER TABLE inference_runs ADD CONSTRAINT uq_inference_run_id_prov UNIQUE (inference_run_id, provenance);

CREATE TABLE inductive_inference_jobs (
    job_id BIGSERIAL NOT NULL, 
    inference_run_id BIGINT NOT NULL, 
    status VARCHAR(30) DEFAULT 'queued' NOT NULL, 
    worker_id VARCHAR(160), 
    lease_token VARCHAR(160), 
    lease_expires_at TIMESTAMP WITH TIME ZONE, 
    attempt_count INTEGER DEFAULT '0' NOT NULL, 
    max_attempts INTEGER DEFAULT '5' NOT NULL, 
    priority INTEGER DEFAULT '100' NOT NULL, 
    next_attempt_at TIMESTAMP WITH TIME ZONE, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    last_error_code VARCHAR(100), 
    last_error TEXT, 
    provenance VARCHAR(30) DEFAULT 'real' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (job_id), 
    CONSTRAINT ck_inductive_job_status CHECK (status IN ('queued','running','succeeded','retry_wait','failed','cancelled')), 
    CONSTRAINT ck_inductive_job_attempt_count CHECK (attempt_count >= 0), 
    CONSTRAINT ck_inductive_job_max_attempts CHECK (max_attempts > 0), 
    CONSTRAINT ck_inductive_job_provenance CHECK (provenance IN ('real','synthetic_demo')), 
    CONSTRAINT uq_inductive_job_run UNIQUE (inference_run_id), 
    CONSTRAINT fk_inductive_job_run_prov FOREIGN KEY(inference_run_id, provenance) REFERENCES inference_runs (inference_run_id, provenance) ON DELETE CASCADE
);

CREATE INDEX ix_inductive_jobs_due ON inductive_inference_jobs (status, next_attempt_at);

CREATE INDEX ix_inductive_jobs_lease ON inductive_inference_jobs (status, lease_expires_at);

CREATE TABLE inductive_prediction_evidence (
    evidence_id BIGSERIAL NOT NULL, 
    fraud_prediction_id BIGINT NOT NULL, 
    graph_snapshot_id BIGINT NOT NULL, 
    relation_schema_version VARCHAR(120) NOT NULL, 
    context_cutoff_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    neighbor_counts JSONB DEFAULT '{}' NOT NULL, 
    historic_review_ids JSONB DEFAULT '[]' NOT NULL, 
    stitched_graph_sha256 VARCHAR(64) NOT NULL, 
    input_feature_sha256 VARCHAR(64) NOT NULL, 
    embedding_sha256 VARCHAR(64) NOT NULL, 
    bundle_manifest_sha256 VARCHAR(64) NOT NULL, 
    provenance VARCHAR(30) DEFAULT 'real' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (evidence_id), 
    CONSTRAINT uq_inductive_evidence_prediction UNIQUE (fraud_prediction_id), 
    CONSTRAINT ck_inductive_evidence_provenance CHECK (provenance IN ('real','synthetic_demo')), 
    CONSTRAINT ck_inductive_stitched_graph_sha256 CHECK (length(stitched_graph_sha256) = 64 AND lower(stitched_graph_sha256) = stitched_graph_sha256), 
    CONSTRAINT ck_inductive_input_feature_sha256 CHECK (length(input_feature_sha256) = 64 AND lower(input_feature_sha256) = input_feature_sha256), 
    CONSTRAINT ck_inductive_embedding_sha256 CHECK (length(embedding_sha256) = 64 AND lower(embedding_sha256) = embedding_sha256), 
    CONSTRAINT ck_inductive_bundle_manifest_sha256 CHECK (length(bundle_manifest_sha256) = 64 AND lower(bundle_manifest_sha256) = bundle_manifest_sha256), 
    CONSTRAINT fk_inductive_evidence_prediction FOREIGN KEY(fraud_prediction_id) REFERENCES fraud_predictions (fraud_prediction_id) ON DELETE CASCADE, 
    CONSTRAINT fk_inductive_evidence_snapshot FOREIGN KEY(graph_snapshot_id) REFERENCES graph_snapshots (graph_snapshot_id) ON DELETE RESTRICT
);

CREATE INDEX ix_inductive_evidence_snapshot ON inductive_prediction_evidence (graph_snapshot_id);

CREATE INDEX ix_inductive_evidence_cutoff ON inductive_prediction_evidence (context_cutoff_at);

UPDATE alembic_version SET version_num='0005_inductive_batch_scoring' WHERE alembic_version.version_num = '0004_synthetic_campaigns';

-- Running upgrade 0005_inductive_batch_scoring -> 0006_batch_filenames

ALTER TABLE batch_analyses ADD COLUMN source_filename VARCHAR(255);

UPDATE alembic_version SET version_num='0006_batch_filenames' WHERE alembic_version.version_num = '0005_inductive_batch_scoring';

-- Running upgrade 0006_batch_filenames -> 0007_database_features

CREATE VIEW vw_batch_analysis_summary AS
    SELECT b.batch_analysis_id, b.requested_by_user_id, b.source_filename,
           b.status, b.row_count, b.accepted_count, b.rejected_count,
           b.inference_run_id, COUNT(p.fraud_prediction_id) AS scored_count,
           COALESCE(SUM(CASE WHEN p.predicted_label = 1 THEN 1 ELSE 0 END),0) AS flagged_count,
           AVG(p.risk_score) AS mean_risk
    FROM batch_analyses b LEFT JOIN fraud_predictions p
      ON p.inference_run_id = b.inference_run_id
    GROUP BY b.batch_analysis_id, b.requested_by_user_id, b.source_filename,
             b.status, b.row_count, b.accepted_count, b.rejected_count, b.inference_run_id;

CREATE VIEW vw_product_review_summary AS
    SELECT p.product_id, p.source_system, p.external_product_key, p.display_name,
           COUNT(r.review_id) AS review_count, AVG(r.rating) AS mean_rating
    FROM products p LEFT JOIN reviews r ON r.product_id = p.product_id
    GROUP BY p.product_id, p.source_system, p.external_product_key, p.display_name;

CREATE INDEX ix_feedback_owner_status ON review_feedback (submitted_by_user_id, status, created_at);

CREATE FUNCTION audit_review_feedback() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_data jsonb; new_data jsonb; actor bigint; record_key bigint;
BEGIN
  actor := NULLIF(current_setting('neurograph.actor_id', true), '')::bigint;
  IF TG_OP <> 'INSERT' THEN
    old_data := jsonb_build_object('review_id', OLD.review_id,
      'submitted_by_user_id', OLD.submitted_by_user_id, 'feedback_type', OLD.feedback_type,
      'ground_truth_label', OLD.ground_truth_label, 'status', OLD.status);
    record_key := OLD.feedback_id;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    new_data := jsonb_build_object('review_id', NEW.review_id,
      'submitted_by_user_id', NEW.submitted_by_user_id, 'feedback_type', NEW.feedback_type,
      'ground_truth_label', NEW.ground_truth_label, 'status', NEW.status);
    record_key := NEW.feedback_id;
  END IF;
  INSERT INTO audit_logs(actor_user_id, action, entity_type, entity_key, before_data, after_data)
  VALUES (actor, 'feedback.' || lower(TG_OP), 'review_feedback', record_key::text, old_data, new_data);
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;

CREATE TRIGGER trg_review_feedback_audit AFTER INSERT OR UPDATE OR DELETE ON review_feedback FOR EACH ROW EXECUTE FUNCTION audit_review_feedback();

CREATE PROCEDURE resolve_review_feedback(p_feedback_id bigint, p_actor_id bigint, p_status text)
LANGUAGE plpgsql AS $$
BEGIN
  IF p_status NOT IN ('triaged','resolved','rejected') THEN
    RAISE EXCEPTION 'Invalid feedback resolution' USING ERRCODE = '22023';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM users u JOIN roles r ON r.role_id = u.role_id
                 WHERE u.user_id = p_actor_id AND u.is_active AND r.role_key = 'ADMIN') THEN
    RAISE EXCEPTION 'Administrator required' USING ERRCODE = '42501';
  END IF;
  PERFORM set_config('neurograph.actor_id', p_actor_id::text, true);
  UPDATE review_feedback SET status = p_status WHERE feedback_id = p_feedback_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Feedback not found' USING ERRCODE = 'P0002';
  END IF;
END $$;

REVOKE ALL ON PROCEDURE resolve_review_feedback(bigint, bigint, text) FROM PUBLIC;

UPDATE alembic_version SET version_num='0007_database_features' WHERE alembic_version.version_num = '0006_batch_filenames';

COMMIT;

