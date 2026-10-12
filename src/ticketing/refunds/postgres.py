from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ticketing.orders.postgres import transition_order
from ticketing.orders.service import OrderState


async def refund_order(
    session: AsyncSession, order_id: UUID, amount_minor: int, quantity: int, full: bool = True
) -> UUID:
    existing = (
        await session.execute(
            text(
                "SELECT id FROM refunds WHERE order_id=:order AND amount_minor=:amount "
                "AND quantity=:quantity"
            ),
            {"order": order_id, "amount": amount_minor, "quantity": quantity},
        )
    ).scalar_one_or_none()
    if existing is not None:
        return UUID(str(existing))
    order = (
        await session.execute(
            text("SELECT state,hold_id FROM orders WHERE id=:id FOR UPDATE"), {"id": order_id}
        )
    ).mappings().first()
    if order is None or order["state"] not in {"paid", "ticketed"}:
        raise ValueError("order is not refundable")
    refund_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO refunds(id,order_id,amount_minor,quantity) "
            "VALUES (:id,:order,:amount,:quantity)"
        ),
        {"id": refund_id, "order": order_id, "amount": amount_minor, "quantity": quantity},
    )
    await session.execute(
        text(
            "UPDATE sections s SET sold=s.sold-:quantity "
            "WHERE s.id IN (SELECT section_id FROM hold_items WHERE hold_id=:hold) "
            "AND s.sold >= :quantity"
        ),
        {"hold": order["hold_id"], "quantity": quantity},
    )
    await session.execute(
        text("UPDATE tickets SET state='void' WHERE order_id=:order"), {"order": order_id}
    )
    if full:
        await transition_order(session, order_id, OrderState.REFUNDED, "refund succeeded")
    return refund_id
