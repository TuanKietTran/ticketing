from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ticketing.db.models import Section


async def claim_general_admission(
    session: AsyncSession,
    event_id: UUID,
    section_id: UUID,
    buyer_id: UUID,
    idempotency_key: str,
    quantity: int,
    expires_at: datetime,
) -> UUID | None:
    """Claim inventory with one guarded UPDATE inside the caller's transaction."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    existing = await session.scalar(
        text("SELECT id FROM holds WHERE buyer_id = :buyer AND idempotency_key = :key"),
        {"buyer": buyer_id, "key": idempotency_key},
    )
    if existing is not None:
        return UUID(str(existing))
    result = await session.execute(
        update(Section)
        .where(
            Section.id == section_id,
            Section.event_id == event_id,
            Section.held + Section.sold + quantity <= Section.capacity,
        )
        .values(held=Section.held + quantity)
    )
    if result.rowcount != 1:
        return None
    hold_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO holds(id,event_id,buyer_id,expires_at,status,idempotency_key) "
            "VALUES (:hold,:event,:buyer,:expires,'active',:key)"
        ),
        {
            "hold": hold_id,
            "event": event_id,
            "buyer": buyer_id,
            "expires": expires_at,
            "key": idempotency_key,
        },
    )
    await session.execute(
        text(
            "INSERT INTO hold_items(hold_id, section_id, quantity, unit_amount_minor) "
            "VALUES (:hold, :section, :quantity, 0)"
        ),
        {"hold": hold_id, "section": section_id, "quantity": quantity},
    )
    return hold_id


async def release_expired(session: AsyncSession, now: datetime) -> int:
    """Release only active expired holds and decrement their section counters."""
    rows = (
        await session.execute(
            text(
                "SELECT h.id, hi.section_id, hi.quantity FROM holds h "
                "JOIN hold_items hi ON hi.hold_id = h.id "
                "WHERE h.status = 'active' AND h.expires_at <= :now FOR UPDATE OF h"
            ),
            {"now": now},
        )
    ).all()
    for hold_id, section_id, quantity in rows:
        await session.execute(
            update(Section)
            .where(Section.id == section_id, Section.held >= quantity)
            .values(held=Section.held - quantity)
        )
        await session.execute(
            text("UPDATE holds SET status = 'expired' WHERE id = :id"), {"id": hold_id}
        )
    return len(rows)
