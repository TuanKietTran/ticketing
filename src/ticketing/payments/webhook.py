import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ticketing.orders.postgres import transition_order
from ticketing.orders.service import OrderState
from ticketing.payments.mock import MockPSP


async def receive_webhook(
    session: AsyncSession,
    psp: MockPSP,
    event_id: str,
    raw: str,
    signature: str,
    timestamp: str,
    now: int | None = None,
) -> str:
    """Verify and durably dedupe a webhook before applying a monotonic transition."""
    if not psp.verify(raw, signature, timestamp, now or int(datetime.now(UTC).timestamp())):
        raise ValueError("invalid webhook signature")
    payload = json.loads(raw)
    inserted = await session.execute(
        text(
            "INSERT INTO webhook_events(provider_event_id,verified,payload) "
            "VALUES (:id,true,CAST(:payload AS jsonb)) ON CONFLICT DO NOTHING"
        ),
        {"id": event_id, "payload": raw},
    )
    if inserted.rowcount == 0:
        return "duplicate"
    order_id = UUID(str(payload["order_id"]))
    state = OrderState.PAID if payload.get("status") == "succeeded" else OrderState.FAILED
    await transition_order(session, order_id, state, f"webhook {event_id}")
    await session.execute(
        text("UPDATE webhook_events SET processed_at=now() WHERE provider_event_id=:id"),
        {"id": event_id},
    )
    return "processed"


async def reconcile_charges(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            text(
                "SELECT c.order_id,c.state,o.state AS order_state FROM charges c "
                "JOIN orders o ON o.id=c.order_id WHERE c.state='succeeded' "
                "AND o.state NOT IN ('paid','ticketed')"
            )
        )
    ).all()
    for order_id, _charge_state, _order_state in rows:
        await transition_order(session, order_id, OrderState.PAID, "reconciliation")
    return len(rows)
