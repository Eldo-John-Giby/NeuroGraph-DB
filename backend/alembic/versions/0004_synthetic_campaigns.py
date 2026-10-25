"""Add provenance-scoped synthetic campaign records and evidence links.

Revision ID: 0004_synthetic_campaigns
Revises: 0003_add_provenance_tracking
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_synthetic_campaigns"
down_revision = "0003_add_provenance_tracking"
branch_labels = None
depends_on = None

ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    with op.batch_alter_table("graph_snapshots") as batch:
        batch.add_column(sa.Column("provenance", sa.String(30), server_default="real", nullable=False))
        batch.create_check_constraint("ck_graph_snapshot_provenance", "provenance IN ('real','synthetic_demo')")

    op.create_table(
        "synthetic_campaigns",
        sa.Column("synthetic_campaign_id", ID, primary_key=True),
        sa.Column("campaign_key", sa.String(160), nullable=False, unique=True),
        sa.Column("campaign_name", sa.String(200), nullable=False),
        sa.Column("product_id", ID, nullable=False),
        sa.Column("prior_campaign_id", ID, nullable=True),
        sa.Column("prior_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prior_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attack_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attack_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("provenance", sa.String(30), server_default="synthetic_demo", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("provenance = 'synthetic_demo'", name="ck_campaign_provenance"),
        sa.CheckConstraint("attack_start_at < attack_end_at", name="ck_campaign_attack_window"),
        sa.CheckConstraint("prior_start_at < prior_end_at", name="ck_campaign_prior_window"),
        sa.CheckConstraint("prior_end_at <= attack_start_at", name="ck_campaign_windows_order"),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prior_campaign_id"], ["synthetic_campaigns.synthetic_campaign_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_campaign_product_attack", "synthetic_campaigns", ["product_id", "attack_start_at", "attack_end_at"])

    op.create_table(
        "synthetic_campaign_members",
        sa.Column("synthetic_campaign_member_id", ID, primary_key=True),
        sa.Column("synthetic_campaign_id", ID, nullable=False),
        sa.Column("reviewer_id", ID, nullable=False),
        sa.Column("membership_type", sa.String(30), nullable=False),
        sa.Column("provenance", sa.String(30), server_default="synthetic_demo", nullable=False),
        sa.CheckConstraint("provenance = 'synthetic_demo'", name="ck_campaign_member_provenance"),
        sa.CheckConstraint("membership_type IN ('attack_participant','prior_participant')", name="ck_campaign_member_type"),
        sa.ForeignKeyConstraint(["synthetic_campaign_id"], ["synthetic_campaigns.synthetic_campaign_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["reviewers.reviewer_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("synthetic_campaign_id", "reviewer_id", name="uq_campaign_member_reviewer"),
    )
    op.create_index("ix_campaign_members_reviewer", "synthetic_campaign_members", ["reviewer_id", "synthetic_campaign_id"])

    op.create_table(
        "synthetic_campaign_reviews",
        sa.Column("synthetic_campaign_review_id", ID, primary_key=True),
        sa.Column("synthetic_campaign_id", ID, nullable=False),
        sa.Column("review_id", ID, nullable=False),
        sa.Column("campaign_period", sa.String(20), nullable=False),
        sa.Column("evidence_note", sa.Text(), nullable=False),
        sa.Column("provenance", sa.String(30), server_default="synthetic_demo", nullable=False),
        sa.CheckConstraint("provenance = 'synthetic_demo'", name="ck_campaign_review_provenance"),
        sa.CheckConstraint("campaign_period IN ('attack','prior')", name="ck_campaign_review_period"),
        sa.ForeignKeyConstraint(["synthetic_campaign_id"], ["synthetic_campaigns.synthetic_campaign_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.review_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("synthetic_campaign_id", "review_id", name="uq_campaign_review"),
    )
    op.create_index("ix_campaign_reviews_period", "synthetic_campaign_reviews", ["synthetic_campaign_id", "campaign_period", "review_id"])


def downgrade() -> None:
    op.drop_index("ix_campaign_reviews_period", table_name="synthetic_campaign_reviews")
    op.drop_table("synthetic_campaign_reviews")
    op.drop_index("ix_campaign_members_reviewer", table_name="synthetic_campaign_members")
    op.drop_table("synthetic_campaign_members")
    op.drop_index("ix_campaign_product_attack", table_name="synthetic_campaigns")
    op.drop_table("synthetic_campaigns")
    with op.batch_alter_table("graph_snapshots") as batch:
        batch.drop_constraint("ck_graph_snapshot_provenance", type_="check")
        batch.drop_column("provenance")
