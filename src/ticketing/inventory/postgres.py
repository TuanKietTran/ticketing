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
    hold_id = uuid4()
    result = await session.execute(
        text(
            "WITH existing AS ("
            "  SELECT id FROM holds WHERE buyer_id=:buyer AND idempotency_key=:key"
            "), updated AS ("
            "  UPDATE sections SET held=held+:quantity "
            "  WHERE id=:section AND event_id=:event "
            "    AND held+sold+:quantity <= capacity "
            "    AND NOT EXISTS (SELECT 1 FROM existing) "
            "  RETURNING id"
            "), created_hold AS ("
            "  INSERT INTO holds(id,event_id,buyer_id,expires_at,status,idempotency_key) "
            "  SELECT :hold,:event,:buyer,:expires,'active',:key FROM updated "
            "  RETURNING id"
            "), created_item AS ("
            "  INSERT INTO hold_items(hold_id,section_id,quantity,unit_amount_minor) "
            "  SELECT id,:section,:quantity,0 FROM created_hold RETURNING hold_id"
            ") SELECT id FROM existing UNION ALL SELECT id FROM created_hold"
        ),
        {
            "hold": hold_id,
            "event": event_id,
            "section": section_id,
            "buyer": buyer_id,
            "expires": expires_at,
            "key": idempotency_key,
            "quantity": quantity,
        },
    )
    created = result.scalar_one_or_none()
    return UUID(str(created)) if created is not None else None


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
