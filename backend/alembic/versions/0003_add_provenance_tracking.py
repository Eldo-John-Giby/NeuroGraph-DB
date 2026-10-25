"""Add provenance classification and enforce run/model provenance consistency.

Revision ID: 0003_add_provenance_tracking
Revises: 0002_batch_analyses
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_provenance_tracking"
down_revision = "0002_batch_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.add_column(sa.Column("provenance", sa.String(length=30), server_default="real", nullable=False))
        batch_op.create_check_constraint("ck_mv_prov", "provenance IN ('real','synthetic_demo')")
        batch_op.create_check_constraint(
            "ck_mv_demo_not_verified", "provenance = 'real' OR lifecycle_status <> 'verified'"
        )
        batch_op.create_unique_constraint("uq_mv_id_prov", ["model_version_id", "provenance"])

    with op.batch_alter_table("inference_runs") as batch_op:
        batch_op.add_column(sa.Column("provenance", sa.String(length=30), server_default="real", nullable=False))
        batch_op.create_foreign_key(
            "fk_run_model_prov", "model_versions",
            ["model_version_id", "provenance"], ["model_version_id", "provenance"],
        )


def downgrade() -> None:
    with op.batch_alter_table("inference_runs") as batch_op:
        batch_op.drop_constraint("fk_run_model_prov", type_="foreignkey")
        batch_op.drop_column("provenance")
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.drop_constraint("uq_mv_id_prov", type_="unique")
        batch_op.drop_constraint("ck_mv_demo_not_verified", type_="check")
        batch_op.drop_constraint("ck_mv_prov", type_="check")
        batch_op.drop_column("provenance")
