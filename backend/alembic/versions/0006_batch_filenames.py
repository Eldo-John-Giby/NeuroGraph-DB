"""Preserve uploaded CSV filenames for saved analysis history."""
from alembic import op
import sqlalchemy as sa

revision = "0006_batch_filenames"
down_revision = "0005_inductive_batch_scoring"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("batch_analyses", sa.Column("source_filename", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("batch_analyses", "source_filename")
