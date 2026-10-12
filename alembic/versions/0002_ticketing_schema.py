"""Create correctness-critical ticketing schema."""

from alembic import op

revision = "0002_ticketing_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


DDL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS organizers (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, api_key_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS venues (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organizer_id uuid NOT NULL REFERENCES organizers(id), name text NOT NULL);
CREATE TABLE IF NOT EXISTS events (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organizer_id uuid NOT NULL REFERENCES organizers(id), venue_id uuid REFERENCES venues(id), name text NOT NULL, status text NOT NULL DEFAULT 'active', paused boolean NOT NULL DEFAULT false, sale_opens_at timestamptz NOT NULL, sale_closes_at timestamptz NOT NULL, CHECK (sale_closes_at > sale_opens_at));
CREATE TABLE IF NOT EXISTS sections (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), event_id uuid NOT NULL REFERENCES events(id), name text NOT NULL, mode text NOT NULL CHECK (mode IN ('reserved','general_admission')), capacity integer NOT NULL CHECK (capacity >= 0), held integer NOT NULL DEFAULT 0 CHECK (held >= 0), sold integer NOT NULL DEFAULT 0 CHECK (sold >= 0), CHECK (held + sold <= capacity));
CREATE TABLE IF NOT EXISTS seats (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), section_id uuid NOT NULL REFERENCES sections(id), label text NOT NULL, held_until timestamptz, hold_id uuid, sold_order_id uuid, UNIQUE(section_id, label));
CREATE TABLE IF NOT EXISTS holds (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), event_id uuid NOT NULL REFERENCES events(id), buyer_id uuid NOT NULL, expires_at timestamptz NOT NULL, status text NOT NULL DEFAULT 'active', idempotency_key text NOT NULL, UNIQUE(buyer_id, idempotency_key));
CREATE TABLE IF NOT EXISTS hold_items (hold_id uuid NOT NULL REFERENCES holds(id), section_id uuid NOT NULL REFERENCES sections(id), seat_id uuid REFERENCES seats(id), quantity integer NOT NULL CHECK (quantity > 0), unit_amount_minor bigint NOT NULL CHECK (unit_amount_minor >= 0), PRIMARY KEY(hold_id, section_id, seat_id));
CREATE TABLE IF NOT EXISTS orders (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organizer_id uuid NOT NULL REFERENCES organizers(id), event_id uuid NOT NULL REFERENCES events(id), buyer_id uuid NOT NULL, hold_id uuid NOT NULL UNIQUE REFERENCES holds(id), currency char(3) NOT NULL, total_minor bigint NOT NULL CHECK (total_minor >= 0), state text NOT NULL, version integer NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS order_events (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL REFERENCES orders(id), from_state text, to_state text NOT NULL, reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS idempotency_keys (organizer_id uuid, actor_id text NOT NULL, key text NOT NULL, request_hash text NOT NULL, status_code integer, response_json jsonb, claimed_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL, PRIMARY KEY(actor_id, key));
CREATE TABLE IF NOT EXISTS charges (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL REFERENCES orders(id), attempt integer NOT NULL, provider_id text UNIQUE, amount_minor bigint NOT NULL CHECK (amount_minor >= 0), currency char(3) NOT NULL, state text NOT NULL, UNIQUE(order_id, attempt));
CREATE TABLE IF NOT EXISTS tickets (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), order_id uuid NOT NULL REFERENCES orders(id), seat_id uuid, token_hash text NOT NULL UNIQUE, token_payload text NOT NULL, state text NOT NULL DEFAULT 'valid', UNIQUE(order_id, seat_id));
CREATE TABLE IF NOT EXISTS scans (ticket_id uuid PRIMARY KEY REFERENCES tickets(id), scanned_at timestamptz NOT NULL DEFAULT now(), device_id text NOT NULL);
CREATE TABLE IF NOT EXISTS webhook_events (provider_event_id text PRIMARY KEY, received_at timestamptz NOT NULL DEFAULT now(), verified boolean NOT NULL, payload jsonb NOT NULL, processed_at timestamptz);
CREATE TABLE IF NOT EXISTS outbox (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), topic text NOT NULL, aggregate_id uuid, payload jsonb NOT NULL, attempts integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL DEFAULT now(), status text NOT NULL DEFAULT 'pending', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS dead_letters (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), origin text NOT NULL, payload jsonb NOT NULL, error_history jsonb NOT NULL DEFAULT '[]', attempts integer NOT NULL, first_failed_at timestamptz NOT NULL DEFAULT now(), last_failed_at timestamptz NOT NULL DEFAULT now(), status text NOT NULL DEFAULT 'open', discard_reason text);
CREATE INDEX IF NOT EXISTS outbox_ready_idx ON outbox(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS holds_expiry_idx ON holds(status, expires_at);
"""


def upgrade() -> None:
    for statement in DDL.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in ["dead_letters", "outbox", "webhook_events", "scans", "tickets", "charges", "idempotency_keys", "order_events", "orders", "hold_items", "holds", "seats", "sections", "events", "venues", "organizers"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
