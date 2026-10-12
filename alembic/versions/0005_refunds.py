"""Add idempotent refund records."""

from alembic import op

revision = "0005_refunds"
down_revision = "0004_ticket_sets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS refunds "
        "(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL REFERENCES orders(id), "
        "amount_minor bigint NOT NULL CHECK (amount_minor > 0), quantity integer NOT NULL CHECK (quantity > 0), "
        "status text NOT NULL DEFAULT 'succeeded', UNIQUE(order_id, amount_minor, quantity))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refunds")
