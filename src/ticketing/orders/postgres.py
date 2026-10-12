from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ticketing.orders.service import _ALLOWED, OrderState


async def checkout_hold(
    session: AsyncSession,
    hold_id: UUID,
    now: datetime,
    currency: str = "USD",
    total_minor: int = 0,
) -> UUID:
    """Convert an active hold to an order in one transaction."""
    hold = (
        await session.execute(
            text(
                "SELECT h.id,h.event_id,h.buyer_id,e.organizer_id,h.expires_at,h.status "
                "FROM holds h JOIN events e ON e.id=h.event_id WHERE h.id=:id FOR UPDATE"
            ),
            {"id": hold_id},
        )
    ).mappings().first()
    if hold is None or hold["status"] != "active" or hold["expires_at"] <= now:
        raise ValueError("hold is not active")
    order_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO orders(id,organizer_id,event_id,buyer_id,hold_id,currency,total_minor,"
            "state) "
            "VALUES (:id,:org,:event,:buyer,:hold,:currency,:total,'awaiting_payment')"
        ),
        {
            "id": order_id,
            "org": hold["organizer_id"],
            "event": hold["event_id"],
            "buyer": hold["buyer_id"],
            "hold": hold_id,
            "currency": currency,
            "total": total_minor,
        },
    )
    await session.execute(
        text(
            "UPDATE holds SET status='converted' WHERE id=:id AND status='active'"
        ),
        {"id": hold_id},
    )
    await session.execute(
        text(
            "UPDATE sections AS s SET held=s.held-hi.quantity,sold=s.sold+hi.quantity "
            "FROM hold_items hi WHERE hi.hold_id=:hold AND hi.section_id=s.id"
        ),
        {"hold": hold_id},
    )
    await session.execute(
        text(
            "INSERT INTO order_events(order_id,from_state,to_state,reason) "
            "VALUES (:id,'pending','awaiting_payment','hold checkout')"
        ),
        {"id": order_id},
    )
    await session.execute(
        text(
            "INSERT INTO outbox(topic,aggregate_id,payload) "
            "VALUES ('order.awaiting_payment',:id,CAST(:payload AS jsonb))"
        ),
        {"id": order_id, "payload": f'{{"order_id":"{order_id}"}}'},
    )
    return order_id


async def transition_order(
    session: AsyncSession, order_id: UUID, target: OrderState, reason: str
) -> bool:
    row = (
        await session.execute(
            text("SELECT state FROM orders WHERE id=:id FOR UPDATE"), {"id": order_id}
        )
    ).mappings().first()
    if row is None:
        raise KeyError("order not found")
    current = OrderState(row["state"])
    if target not in _ALLOWED[current]:
        return False
    await session.execute(
        text("UPDATE orders SET state=:target,version=version+1 WHERE id=:id"),
        {"target": target.value, "id": order_id},
    )
    await session.execute(
        text(
            "INSERT INTO order_events(order_id,from_state,to_state,reason) "
            "VALUES (:id,:from_state,:to_state,:reason)"
        ),
        {"id": order_id, "from_state": current.value, "to_state": target.value, "reason": reason},
    )
    return True
