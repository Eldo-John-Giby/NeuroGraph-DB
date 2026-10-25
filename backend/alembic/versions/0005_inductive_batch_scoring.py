"""Add PostgreSQL schema support for inductive batch scoring.

Revision ID: 0005_inductive_batch_scoring
Revises: 0004_synthetic_campaigns
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "0005_inductive_batch_scoring"
down_revision = "0004_synthetic_campaigns"
branch_labels = None
depends_on = None

ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql")


def upgrade() -> None:
    # 1. graph_snapshots.context_scope_key required for snapshots permitted for inductive batch context
    with op.batch_alter_table("graph_snapshots") as batch:
        batch.add_column(sa.Column("context_scope_key", sa.String(160), nullable=True))
        batch.create_check_constraint(
            "ck_snapshot_context_scope",
            "NOT batch_context_permitted OR (context_scope_key IS NOT NULL AND length(trim(context_scope_key)) > 0)",
        )

    # 2. model_versions.supported_inference_mode supporting known_node_only and inductive_batch_v1
    with op.batch_alter_table("model_versions") as batch:
        batch.drop_constraint("ck_model_inference_mode", type_="check")
        batch.create_check_constraint(
            "ck_model_inference_mode",
            "supported_inference_mode IN ('known_node_only', 'inductive_batch_v1')",
        )

    # 3. Add composite unique constraint on (inference_run_id, provenance) for provenance preservation
    with op.batch_alter_table("inference_runs") as batch:
        batch.create_unique_constraint("uq_inference_run_id_prov", ["inference_run_id", "provenance"])

    # 4. inductive_inference_jobs: durable leased worker queue linked one-to-one to inference_runs
    op.create_table(
        "inductive_inference_jobs",
        sa.Column("job_id", ID, primary_key=True),
        sa.Column("inference_run_id", ID, nullable=False),
        sa.Column("status", sa.String(30), server_default="queued", nullable=False),
        sa.Column("worker_id", sa.String(160), nullable=True),
        sa.Column("lease_token", sa.String(160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(100), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provenance", sa.String(30), server_default="real", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','retry_wait','failed','cancelled')",
            name="ck_inductive_job_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_inductive_job_attempt_count"),
        sa.CheckConstraint("max_attempts > 0", name="ck_inductive_job_max_attempts"),
        sa.CheckConstraint("provenance IN ('real','synthetic_demo')", name="ck_inductive_job_provenance"),
        sa.UniqueConstraint("inference_run_id", name="uq_inductive_job_run"),
        sa.ForeignKeyConstraint(
            ["inference_run_id", "provenance"],
            ["inference_runs.inference_run_id", "inference_runs.provenance"],
            name="fk_inductive_job_run_prov",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_inductive_jobs_due", "inductive_inference_jobs", ["status", "next_attempt_at"])
    op.create_index("ix_inductive_jobs_lease", "inductive_inference_jobs", ["status", "lease_expires_at"])

    # 5. inductive_prediction_evidence linked one-to-one to fraud_predictions
    op.create_table(
        "inductive_prediction_evidence",
        sa.Column("evidence_id", ID, primary_key=True),
        sa.Column("fraud_prediction_id", ID, nullable=False),
        sa.Column("graph_snapshot_id", ID, nullable=False),
        sa.Column("relation_schema_version", sa.String(120), nullable=False),
        sa.Column("context_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("neighbor_counts", JSON_TYPE, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("historic_review_ids", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("stitched_graph_sha256", sa.String(64), nullable=False),
        sa.Column("input_feature_sha256", sa.String(64), nullable=False),
        sa.Column("embedding_sha256", sa.String(64), nullable=False),
        sa.Column("bundle_manifest_sha256", sa.String(64), nullable=False),
        sa.Column("provenance", sa.String(30), server_default="real", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("fraud_prediction_id", name="uq_inductive_evidence_prediction"),
        sa.CheckConstraint("provenance IN ('real','synthetic_demo')", name="ck_inductive_evidence_provenance"),
        sa.CheckConstraint(
            "length(stitched_graph_sha256) = 64 AND lower(stitched_graph_sha256) = stitched_graph_sha256",
            name="ck_inductive_stitched_graph_sha256",
        ),
        sa.CheckConstraint(
            "length(input_feature_sha256) = 64 AND lower(input_feature_sha256) = input_feature_sha256",
            name="ck_inductive_input_feature_sha256",
        ),
        sa.CheckConstraint(
            "length(embedding_sha256) = 64 AND lower(embedding_sha256) = embedding_sha256",
            name="ck_inductive_embedding_sha256",
        ),
        sa.CheckConstraint(
            "length(bundle_manifest_sha256) = 64 AND lower(bundle_manifest_sha256) = bundle_manifest_sha256",
            name="ck_inductive_bundle_manifest_sha256",
        ),
        sa.ForeignKeyConstraint(
            ["fraud_prediction_id"],
            ["fraud_predictions.fraud_prediction_id"],
            name="fk_inductive_evidence_prediction",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["graph_snapshot_id"],
            ["graph_snapshots.graph_snapshot_id"],
            name="fk_inductive_evidence_snapshot",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_inductive_evidence_snapshot", "inductive_prediction_evidence", ["graph_snapshot_id"])
    op.create_index("ix_inductive_evidence_cutoff", "inductive_prediction_evidence", ["context_cutoff_at"])


def downgrade() -> None:
    op.drop_index("ix_inductive_evidence_cutoff", table_name="inductive_prediction_evidence")
    op.drop_index("ix_inductive_evidence_snapshot", table_name="inductive_prediction_evidence")
    op.drop_table("inductive_prediction_evidence")

    op.drop_index("ix_inductive_jobs_lease", table_name="inductive_inference_jobs")
    op.drop_index("ix_inductive_jobs_due", table_name="inductive_inference_jobs")
    op.drop_table("inductive_inference_jobs")

    with op.batch_alter_table("inference_runs") as batch:
        batch.drop_constraint("uq_inference_run_id_prov", type_="unique")

    with op.batch_alter_table("model_versions") as batch:
        batch.drop_constraint("ck_model_inference_mode", type_="check")
        batch.create_check_constraint(
            "ck_model_inference_mode",
            "supported_inference_mode IN ('known_node_only')",
        )

    with op.batch_alter_table("graph_snapshots") as batch:
        batch.drop_constraint("ck_snapshot_context_scope", type_="check")
        batch.drop_column("context_scope_key")
