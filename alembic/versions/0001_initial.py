"""Create migration bookkeeping."""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TABLE IF NOT EXISTS schema_version (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS schema_version")
