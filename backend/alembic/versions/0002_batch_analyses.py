"""Persist CSV batch analysis requests and row outcomes.

Revision ID: 0002_batch_analyses
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Text
from sqlalchemy.dialects import postgresql

revision = "0002_batch_analyses"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql")


def upgrade():
    op.add_column(
        "graph_snapshots",
        sa.Column("batch_context_permitted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_table(
        "batch_analyses",
        sa.Column("batch_analysis_id", ID, primary_key=True),
        sa.Column("batch_key", sa.Uuid(as_uuid=False), nullable=False, unique=True),
        sa.Column("requested_by_user_id", ID, nullable=True),
        sa.Column("source_system", sa.String(100), nullable=False),
        sa.Column("historic_graph_snapshot_id", ID, nullable=True),
        sa.Column("inference_run_id", ID, nullable=True, unique=True),
        sa.Column("upload_sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("blocking_reasons", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('blocked','queued','running','completed','partial','failed','validation_failed')",
            name="ck_batch_analysis_status",
        ),
        sa.CheckConstraint(
            "row_count >= 0 AND accepted_count >= 0 AND rejected_count >= 0 AND row_count = accepted_count + rejected_count",
            name="ck_batch_analysis_counts",
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["historic_graph_snapshot_id"], ["graph_snapshots.graph_snapshot_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inference_run_id"], ["inference_runs.inference_run_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_batch_analyses_created", "batch_analyses", ["created_at"])
    op.create_table(
        "batch_analysis_rows",
        sa.Column("batch_analysis_row_id", ID, primary_key=True),
        sa.Column("batch_analysis_id", ID, nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("uploaded_review_key", sa.String(255), nullable=True),
        sa.Column("row_state", sa.String(20), nullable=False),
        sa.Column("review_id", ID, nullable=True),
        sa.Column("validation_errors", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("row_state IN ('accepted','rejected')", name="ck_batch_analysis_row_state"),
        sa.CheckConstraint(
            "(row_state = 'accepted' AND review_id IS NOT NULL) OR (row_state = 'rejected' AND review_id IS NULL)",
            name="ck_batch_analysis_row_review",
        ),
        sa.ForeignKeyConstraint(["batch_analysis_id"], ["batch_analyses.batch_analysis_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.review_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("batch_analysis_id", "row_number", name="uq_batch_analysis_row_number"),
    )
    op.create_index("ix_batch_analysis_rows_state", "batch_analysis_rows", ["batch_analysis_id", "row_state", "row_number"])


def downgrade():
    op.drop_index("ix_batch_analysis_rows_state", table_name="batch_analysis_rows")
    op.drop_table("batch_analysis_rows")
    op.drop_index("ix_batch_analyses_created", table_name="batch_analyses")
    op.drop_table("batch_analyses")
    op.drop_column("graph_snapshots", "batch_context_permitted")
