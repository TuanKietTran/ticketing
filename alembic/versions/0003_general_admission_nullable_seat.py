"""Allow general-admission hold rows without a seat."""

from alembic import op

revision = "0003_ga_nullable_seat"
down_revision = "0002_ticketing_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE hold_items DROP CONSTRAINT hold_items_pkey")
    op.execute("ALTER TABLE hold_items ALTER COLUMN seat_id DROP NOT NULL")
    op.execute("ALTER TABLE hold_items ADD PRIMARY KEY (hold_id)")


def downgrade() -> None:
    op.execute("DELETE FROM hold_items WHERE seat_id IS NULL")
    op.execute("ALTER TABLE hold_items DROP CONSTRAINT hold_items_pkey")
    op.execute("ALTER TABLE hold_items ALTER COLUMN seat_id SET NOT NULL")
    op.execute("ALTER TABLE hold_items ADD PRIMARY KEY (hold_id, section_id, seat_id)")
