from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ticketing.orders.postgres import transition_order
from ticketing.orders.service import OrderState


async def record_charge(
    session: AsyncSession,
    order_id: UUID,
    amount_minor: int,
    currency: str,
    provider_id: str,
    attempt: int = 1,
) -> UUID:
    """Insert a charge once; provider and order attempt are natural idempotency keys."""
    existing = (
        await session.execute(
            text("SELECT id FROM charges WHERE order_id=:order AND attempt=:attempt"),
            {"order": order_id, "attempt": attempt},
        )
    ).scalar_one_or_none()
    if existing is not None:
        return UUID(str(existing))
    charge_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO charges(id,order_id,attempt,provider_id,amount_minor,currency,state) "
            "VALUES (:id,:order,:attempt,:provider,:amount,:currency,'succeeded')"
        ),
        {
            "id": charge_id,
            "order": order_id,
            "attempt": attempt,
            "provider": provider_id,
            "amount": amount_minor,
            "currency": currency,
        },
    )
    await transition_order(session, order_id, OrderState.PAID, "provider charge succeeded")
    return charge_id
