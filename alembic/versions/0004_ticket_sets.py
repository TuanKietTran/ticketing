"""Ensure exactly one ticket set per order."""

from alembic import op

revision = "0004_ticket_sets"
down_revision = "0003_ga_nullable_seat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS ticket_sets "
        "(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL UNIQUE REFERENCES orders(id), created_at timestamptz NOT NULL DEFAULT now())"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ticket_sets")
