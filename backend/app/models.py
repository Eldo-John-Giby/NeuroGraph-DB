import uuid
from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
                        Index, Integer, JSON, Numeric, SmallInteger, String, Text, Uuid,
                        UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ID = BigInteger().with_variant(Integer, "sqlite")
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Role(Base):
    __tablename__ = "roles"
    role_id: Mapped[int] = mapped_column(ID, primary_key=True)
    role_key: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email_normalized = lower(trim(email))", name="ck_users_email_normalized"),)
    user_id: Mapped[int] = mapped_column(ID, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id", ondelete="RESTRICT"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionToken(Base):
    __tablename__ = "session_tokens"
    __table_args__ = (
        CheckConstraint("access_expires_at > created_at AND access_expires_at <= refresh_expires_at", name="ck_session_access_expiry"),
        CheckConstraint("refresh_expires_at > created_at", name="ck_session_refresh_expiry"),
        Index("ix_session_tokens_active", "user_id", "refresh_expires_at", postgresql_where=text("revoked_at IS NULL")),
    )
    session_token_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    access_jti_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_session_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("session_tokens.session_token_id", ondelete="SET NULL"))


class Reviewer(Base):
    __tablename__ = "reviewers"
    __table_args__ = (UniqueConstraint("source_system", "external_reviewer_key", name="uq_reviewers_source_key"),)
    reviewer_id: Mapped[int] = mapped_column(ID, primary_key=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_reviewer_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("source_system", "external_product_key", name="uq_products_source_key"),)
    product_id: Mapped[int] = mapped_column(ID, primary_key=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    external_product_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("(source_system IS NULL) = (source_review_key IS NULL)", name="ck_reviews_source_pair"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        CheckConstraint("ground_truth_label IS NULL OR ground_truth_label IN (0, 1)", name="ck_reviews_ground_truth"),
        Index("uq_reviews_source_pair", "source_system", "source_review_key", unique=True, postgresql_where=text("source_system IS NOT NULL")),
        Index("ix_reviews_product_date", "product_id", "reviewed_at"),
        Index("ix_reviews_reviewer_date", "reviewer_id", "reviewed_at"),
    )
    review_id: Mapped[int] = mapped_column(ID, primary_key=True)
    source_system: Mapped[str | None] = mapped_column(String(100))
    source_review_key: Mapped[str | None] = mapped_column(String(255))
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("reviewers.reviewer_id", ondelete="SET NULL"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.product_id", ondelete="SET NULL"), index=True)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_text: Mapped[str | None] = mapped_column(Text)
    ground_truth_label: Mapped[int | None] = mapped_column(SmallInteger)
    label_source: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReviewVariant(Base):
    __tablename__ = "review_variants"
    __table_args__ = (UniqueConstraint("review_id", "variant_key", name="uq_review_variants_key"),)
    review_variant_id: Mapped[int] = mapped_column(ID, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.review_id", ondelete="CASCADE"), nullable=False)
    variant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    variant_type: Mapped[str] = mapped_column(String(80), nullable=False)
    variant_text: Mapped[str | None] = mapped_column(Text)
    review_metadata: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PreprocessingVersion(Base):
    __tablename__ = "preprocessing_versions"
    __table_args__ = (
        CheckConstraint("lifecycle_status IN ('registered','verified','retired','unavailable')", name="ck_preprocessing_status"),
        CheckConstraint("length(preprocessing_sha256) = 64 AND lower(preprocessing_sha256) = preprocessing_sha256", name="ck_preprocessing_sha256"),
    )
    preprocessing_version_id: Mapped[int] = mapped_column(ID, primary_key=True)
    version_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    preprocessing_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    preprocessing_config: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'{}'"))
    code_revision: Mapped[str] = mapped_column(String(160), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        CheckConstraint("supported_inference_mode IN ('known_node_only', 'inductive_batch_v1')", name="ck_model_inference_mode"),
        CheckConstraint("lifecycle_status IN ('unavailable','registered','verified','retired')", name="ck_model_lifecycle"),
        CheckConstraint("recommended_threshold IS NULL OR recommended_threshold BETWEEN 0 AND 1", name="ck_model_threshold"),
        CheckConstraint("length(config_sha256) = 64 AND lower(config_sha256) = config_sha256", name="ck_model_config_sha256"),
        CheckConstraint("checkpoint_sha256 IS NULL OR (length(checkpoint_sha256) = 64 AND lower(checkpoint_sha256) = checkpoint_sha256)", name="ck_model_checkpoint_sha256"),
        CheckConstraint("lifecycle_status <> 'verified' OR (checkpoint_uri IS NOT NULL AND checkpoint_sha256 IS NOT NULL AND recommended_threshold IS NOT NULL AND threshold_source IS NOT NULL AND verification_at IS NOT NULL)", name="ck_model_verified_requirements"),
        CheckConstraint("provenance IN ('real','synthetic_demo')", name="ck_mv_prov"),
        CheckConstraint("provenance = 'real' OR lifecycle_status <> 'verified'", name="ck_mv_demo_not_verified"),
        UniqueConstraint("model_version_id", "provenance", name="uq_mv_id_prov"),
    )
    model_version_id: Mapped[int] = mapped_column(ID, primary_key=True)
    version_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    architecture_version: Mapped[str] = mapped_column(String(100), nullable=False)
    architecture_config: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'{}'"))
    config_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_uri: Mapped[str | None] = mapped_column(Text)
    checkpoint_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    preprocessing_version_id: Mapped[int] = mapped_column(ForeignKey("preprocessing_versions.preprocessing_version_id", ondelete="RESTRICT"), nullable=False, index=True)
    input_contract_version: Mapped[str] = mapped_column(String(100), nullable=False)
    supported_inference_mode: Mapped[str] = mapped_column(String(50), nullable=False, server_default="known_node_only")
    recommended_threshold: Mapped[float | None] = mapped_column(Numeric(8, 7))
    threshold_source: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unavailable")
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="real")
    verification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GraphSnapshot(Base):
    __tablename__ = "graph_snapshots"
    __table_args__ = (
        CheckConstraint("node_count >= 0", name="ck_graph_snapshot_node_count"),
        CheckConstraint("storage_status IN ('available','archived','missing')", name="ck_graph_snapshot_storage"),
        CheckConstraint("length(dataset_sha256) = 64 AND lower(dataset_sha256) = dataset_sha256", name="ck_graph_dataset_sha256"),
        CheckConstraint("length(artifact_sha256) = 64 AND lower(artifact_sha256) = artifact_sha256", name="ck_graph_artifact_sha256"),
        CheckConstraint("provenance IN ('real','synthetic_demo')", name="ck_graph_snapshot_provenance"),
        CheckConstraint("NOT batch_context_permitted OR (context_scope_key IS NOT NULL AND length(trim(context_scope_key)) > 0)", name="ck_snapshot_context_scope"),
    )
    graph_snapshot_id: Mapped[int] = mapped_column(ID, primary_key=True)
    snapshot_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    graph_builder_version: Mapped[str] = mapped_column(String(160), nullable=False)
    relation_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    split_protocol_key: Mapped[str] = mapped_column(String(160), nullable=False)
    node_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    edge_counts: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    storage_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="available")
    batch_context_permitted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    context_scope_key: Mapped[str | None] = mapped_column(String(160))
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="real")


class SyntheticCampaign(Base):
    __tablename__ = "synthetic_campaigns"
    __table_args__ = (
        CheckConstraint("provenance = 'synthetic_demo'", name="ck_campaign_provenance"),
        CheckConstraint("attack_start_at < attack_end_at", name="ck_campaign_attack_window"),
        CheckConstraint("prior_start_at < prior_end_at", name="ck_campaign_prior_window"),
        CheckConstraint("prior_end_at <= attack_start_at", name="ck_campaign_windows_order"),
        Index("ix_campaign_product_attack", "product_id", "attack_start_at", "attack_end_at"),
    )
    synthetic_campaign_id: Mapped[int] = mapped_column(ID, primary_key=True)
    campaign_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    campaign_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id", ondelete="RESTRICT"), nullable=False)
    prior_campaign_id: Mapped[int | None] = mapped_column(ForeignKey("synthetic_campaigns.synthetic_campaign_id", ondelete="SET NULL"))
    prior_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prior_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attack_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attack_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="synthetic_demo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SyntheticCampaignMember(Base):
    __tablename__ = "synthetic_campaign_members"
    __table_args__ = (
        CheckConstraint("provenance = 'synthetic_demo'", name="ck_campaign_member_provenance"),
        CheckConstraint("membership_type IN ('attack_participant','prior_participant')", name="ck_campaign_member_type"),
        UniqueConstraint("synthetic_campaign_id", "reviewer_id", name="uq_campaign_member_reviewer"),
        Index("ix_campaign_members_reviewer", "reviewer_id", "synthetic_campaign_id"),
    )
    synthetic_campaign_member_id: Mapped[int] = mapped_column(ID, primary_key=True)
    synthetic_campaign_id: Mapped[int] = mapped_column(ForeignKey("synthetic_campaigns.synthetic_campaign_id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("reviewers.reviewer_id", ondelete="RESTRICT"), nullable=False)
    membership_type: Mapped[str] = mapped_column(String(30), nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="synthetic_demo")


class SyntheticCampaignReview(Base):
    __tablename__ = "synthetic_campaign_reviews"
    __table_args__ = (
        CheckConstraint("provenance = 'synthetic_demo'", name="ck_campaign_review_provenance"),
        CheckConstraint("campaign_period IN ('attack','prior')", name="ck_campaign_review_period"),
        UniqueConstraint("synthetic_campaign_id", "review_id", name="uq_campaign_review"),
        Index("ix_campaign_reviews_period", "synthetic_campaign_id", "campaign_period", "review_id"),
    )
    synthetic_campaign_review_id: Mapped[int] = mapped_column(ID, primary_key=True)
    synthetic_campaign_id: Mapped[int] = mapped_column(ForeignKey("synthetic_campaigns.synthetic_campaign_id", ondelete="CASCADE"), nullable=False)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.review_id", ondelete="RESTRICT"), nullable=False)
    campaign_period: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_note: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="synthetic_demo")


class GraphSnapshotReview(Base):
    __tablename__ = "graph_snapshot_reviews"
    __table_args__ = (CheckConstraint("split IN ('train','validation','test')", name="ck_snapshot_review_split"), Index("ix_snapshot_review_split", "graph_snapshot_id", "split", "review_id"))
    graph_snapshot_id: Mapped[int] = mapped_column(ForeignKey("graph_snapshots.graph_snapshot_id", ondelete="CASCADE"), primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.review_id", ondelete="RESTRICT"), primary_key=True)
    split: Mapped[str] = mapped_column(String(20), nullable=False)


class InferenceRun(Base):
    __tablename__ = "inference_runs"
    __table_args__ = (
        CheckConstraint("threshold BETWEEN 0 AND 1", name="ck_inference_threshold"),
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_inference_status"),
        CheckConstraint("idempotency_key IS NULL OR requested_by_user_id IS NOT NULL", name="ck_inference_idempotency_owner"),
        CheckConstraint("requested_count > 0 AND completed_count >= 0 AND completed_count <= requested_count", name="ck_inference_counts"),
        UniqueConstraint("requested_by_user_id", "idempotency_key", name="uq_inference_user_idempotency"),
        UniqueConstraint("inference_run_id", "provenance", name="uq_inference_run_id_prov"),
        ForeignKeyConstraint(["model_version_id", "provenance"],
                             ["model_versions.model_version_id", "model_versions.provenance"],
                             name="fk_run_model_prov"),
    )
    inference_run_id: Mapped[int] = mapped_column(ID, primary_key=True)
    run_key: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.model_version_id", ondelete="RESTRICT"), nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="real")
    graph_snapshot_id: Mapped[int] = mapped_column(ForeignKey("graph_snapshots.graph_snapshot_id", ondelete="RESTRICT"), nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    threshold: Mapped[float] = mapped_column(Numeric(8, 7), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="queued")
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BatchAnalysis(Base):
    __tablename__ = "batch_analyses"
    __table_args__ = (
        CheckConstraint("status IN ('blocked','queued','running','completed','partial','failed','validation_failed')", name="ck_batch_analysis_status"),
        CheckConstraint("row_count >= 0 AND accepted_count >= 0 AND rejected_count >= 0 AND row_count = accepted_count + rejected_count", name="ck_batch_analysis_counts"),
        Index("ix_batch_analyses_created", "created_at"),
    )
    batch_analysis_id: Mapped[int] = mapped_column(ID, primary_key=True)
    batch_key: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"))
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    historic_graph_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("graph_snapshots.graph_snapshot_id", ondelete="RESTRICT"))
    inference_run_id: Mapped[int | None] = mapped_column(ForeignKey("inference_runs.inference_run_id", ondelete="RESTRICT"), unique=True)
    upload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    blocking_reasons: Mapped[list[str]] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'[]'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BatchAnalysisRow(Base):
    __tablename__ = "batch_analysis_rows"
    __table_args__ = (
        CheckConstraint("row_state IN ('accepted','rejected')", name="ck_batch_analysis_row_state"),
        CheckConstraint("(row_state = 'accepted' AND review_id IS NOT NULL) OR (row_state = 'rejected' AND review_id IS NULL)", name="ck_batch_analysis_row_review"),
        UniqueConstraint("batch_analysis_id", "row_number", name="uq_batch_analysis_row_number"),
        Index("ix_batch_analysis_rows_state", "batch_analysis_id", "row_state", "row_number"),
    )
    batch_analysis_row_id: Mapped[int] = mapped_column(ID, primary_key=True)
    batch_analysis_id: Mapped[int] = mapped_column(ForeignKey("batch_analyses.batch_analysis_id", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_review_key: Mapped[str | None] = mapped_column(String(255))
    row_state: Mapped[str] = mapped_column(String(20), nullable=False)
    review_id: Mapped[int | None] = mapped_column(ForeignKey("reviews.review_id", ondelete="RESTRICT"))
    validation_errors: Mapped[list[dict]] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'[]'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FraudPrediction(Base):
    __tablename__ = "fraud_predictions"
    __table_args__ = (
        UniqueConstraint("inference_run_id", "review_id", name="uq_predictions_run_review"),
        CheckConstraint("risk_score BETWEEN 0 AND 1", name="ck_prediction_score"),
        CheckConstraint("predicted_label IN (0,1)", name="ck_prediction_label"),
        Index("ix_predictions_review_created", "review_id", "created_at"),
    )
    fraud_prediction_id: Mapped[int] = mapped_column(ID, primary_key=True)
    inference_run_id: Mapped[int] = mapped_column(ForeignKey("inference_runs.inference_run_id", ondelete="RESTRICT"), nullable=False)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.review_id", ondelete="RESTRICT"), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(9, 8), nullable=False)
    predicted_label: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    attention_weights: Mapped[dict | None] = mapped_column(JSON_TYPE)
    graph_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="not_requested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewFeedback(Base):
    __tablename__ = "review_feedback"
    __table_args__ = (
        CheckConstraint("feedback_type IN ('label_correction','review_quality','other')", name="ck_feedback_type"),
        CheckConstraint("status IN ('submitted','triaged','resolved','rejected')", name="ck_feedback_status"),
        CheckConstraint("ground_truth_label IS NULL OR ground_truth_label IN (0,1)", name="ck_feedback_label"),
        CheckConstraint("idempotency_key IS NULL OR submitted_by_user_id IS NOT NULL", name="ck_feedback_idempotency_owner"),
        UniqueConstraint("submitted_by_user_id", "idempotency_key", name="uq_feedback_user_idempotency"),
    )
    feedback_id: Mapped[int] = mapped_column(ID, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.review_id", ondelete="RESTRICT"), nullable=False)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"))
    feedback_type: Mapped[str] = mapped_column(String(40), nullable=False)
    ground_truth_label: Mapped[int | None] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GraphSyncJob(Base):
    __tablename__ = "graph_sync_jobs"
    __table_args__ = (
        CheckConstraint("(operation IN ('review_upsert','review_delete') AND review_id IS NOT NULL AND graph_snapshot_id IS NULL) OR (operation = 'snapshot_rebuild' AND review_id IS NULL AND graph_snapshot_id IS NOT NULL)", name="ck_graph_job_scope"),
        CheckConstraint("idempotency_key IS NULL OR requested_by_user_id IS NOT NULL", name="ck_graph_job_idempotency_owner"),
        CheckConstraint("status IN ('queued','running','succeeded','retry_wait','failed','cancelled')", name="ck_graph_job_status"),
        CheckConstraint("attempt_count >= 0", name="ck_graph_job_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_graph_job_max_attempts"),
        UniqueConstraint("requested_by_user_id", "idempotency_key", name="uq_graph_job_user_idempotency"),
        UniqueConstraint("source_event_key", name="uq_graph_job_source_event"),
        Index("ix_graph_jobs_due", "status", "next_attempt_at", postgresql_where=text("status IN ('queued','retry_wait')")),
    )
    graph_sync_job_id: Mapped[int] = mapped_column(ID, primary_key=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    review_id: Mapped[int | None] = mapped_column(ForeignKey("reviews.review_id", ondelete="RESTRICT"))
    graph_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("graph_snapshots.graph_snapshot_id", ondelete="RESTRICT"))
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"))
    source_event_key: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_log_id: Mapped[int] = mapped_column(ID, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(200), nullable=False)
    before_data: Mapped[dict | None] = mapped_column(JSON_TYPE)
    after_data: Mapped[dict | None] = mapped_column(JSON_TYPE)
    request_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InductiveInferenceJob(Base):
    __tablename__ = "inductive_inference_jobs"
    __table_args__ = (
        UniqueConstraint("inference_run_id", name="uq_inductive_job_run"),
        CheckConstraint("status IN ('queued','running','succeeded','retry_wait','failed','cancelled')", name="ck_inductive_job_status"),
        CheckConstraint("attempt_count >= 0", name="ck_inductive_job_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_inductive_job_max_attempts"),
        CheckConstraint("provenance IN ('real','synthetic_demo')", name="ck_inductive_job_provenance"),
        ForeignKeyConstraint(
            ["inference_run_id", "provenance"],
            ["inference_runs.inference_run_id", "inference_runs.provenance"],
            name="fk_inductive_job_run_prov",
            ondelete="CASCADE",
        ),
        Index("ix_inductive_jobs_due", "status", "next_attempt_at"),
        Index("ix_inductive_jobs_lease", "status", "lease_expires_at"),
    )
    job_id: Mapped[int] = mapped_column(ID, primary_key=True)
    inference_run_id: Mapped[int] = mapped_column(ID, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="queued")
    worker_id: Mapped[str | None] = mapped_column(String(160))
    lease_token: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="real")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InductivePredictionEvidence(Base):
    __tablename__ = "inductive_prediction_evidence"
    __table_args__ = (
        UniqueConstraint("fraud_prediction_id", name="uq_inductive_evidence_prediction"),
        CheckConstraint("provenance IN ('real','synthetic_demo')", name="ck_inductive_evidence_provenance"),
        CheckConstraint(
            "length(stitched_graph_sha256) = 64 AND lower(stitched_graph_sha256) = stitched_graph_sha256",
            name="ck_inductive_stitched_graph_sha256",
        ),
        CheckConstraint(
            "length(input_feature_sha256) = 64 AND lower(input_feature_sha256) = input_feature_sha256",
            name="ck_inductive_input_feature_sha256",
        ),
        CheckConstraint(
            "length(embedding_sha256) = 64 AND lower(embedding_sha256) = embedding_sha256",
            name="ck_inductive_embedding_sha256",
        ),
        CheckConstraint(
            "length(bundle_manifest_sha256) = 64 AND lower(bundle_manifest_sha256) = bundle_manifest_sha256",
            name="ck_inductive_bundle_manifest_sha256",
        ),
        ForeignKeyConstraint(
            ["fraud_prediction_id"],
            ["fraud_predictions.fraud_prediction_id"],
            name="fk_inductive_evidence_prediction",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["graph_snapshot_id"],
            ["graph_snapshots.graph_snapshot_id"],
            name="fk_inductive_evidence_snapshot",
            ondelete="RESTRICT",
        ),
        Index("ix_inductive_evidence_snapshot", "graph_snapshot_id"),
        Index("ix_inductive_evidence_cutoff", "context_cutoff_at"),
    )
    evidence_id: Mapped[int] = mapped_column(ID, primary_key=True)
    fraud_prediction_id: Mapped[int] = mapped_column(ID, nullable=False, unique=True)
    graph_snapshot_id: Mapped[int] = mapped_column(ID, nullable=False)
    relation_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    context_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    neighbor_counts: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'{}'"))
    historic_review_ids: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, server_default=text("'[]'"))
    stitched_graph_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    input_feature_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, server_default="real")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


