import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_dead_letters(session: AsyncSession, limit: int = 100) -> list[dict[str, object]]:
    rows = await session.execute(
        text(
            "SELECT id,origin,payload,error_history,attempts,status,first_failed_at,last_failed_at "
            "FROM dead_letters ORDER BY first_failed_at LIMIT :limit"
        ),
        {"limit": min(max(limit, 1), 1000)},
    )
    return [dict(row) for row in rows.mappings()]


async def replay_dead_letter(session: AsyncSession, item_id: UUID) -> bool:
    row = (
        await session.execute(
            text("SELECT payload,status FROM dead_letters WHERE id=:id FOR UPDATE"), {"id": item_id}
        )
    ).mappings().first()
    if row is None or row["status"] != "open":
        return False
    await session.execute(
        text(
            "INSERT INTO outbox(topic,payload) "
            "VALUES ('dead_letter.replay',CAST(:payload AS jsonb))"
        ),
        {"payload": json.dumps(row["payload"])},
    )
    await session.execute(
        text("UPDATE dead_letters SET status='replayed' WHERE id=:id AND status='open'"),
        {"id": item_id},
    )
    return True


async def discard_dead_letter(session: AsyncSession, item_id: UUID, reason: str) -> bool:
    result = await session.execute(
        text(
            "UPDATE dead_letters SET status='discarded',discard_reason=:reason "
            "WHERE id=:id AND status='open'"
        ),
        {"id": item_id, "reason": reason[:500]},
    )
    return result.rowcount == 1
