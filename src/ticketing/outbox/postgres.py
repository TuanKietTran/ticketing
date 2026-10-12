import json
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def enqueue(
    session: AsyncSession, topic: str, payload: dict[str, object], aggregate_id: UUID | None = None
) -> UUID:
    result = await session.execute(
        text(
            "INSERT INTO outbox(topic,aggregate_id,payload) "
            "VALUES (:topic,:aggregate,CAST(:payload AS jsonb)) "
            "RETURNING id"
        ),
        {"topic": topic, "aggregate": aggregate_id, "payload": json.dumps(payload)},
    )
    return result.scalar_one()


async def dispatch_once(
    sessions: async_sessionmaker[AsyncSession],
    consumer: Callable[[str, dict[str, object]], Awaitable[None]],
    max_attempts: int = 5,
) -> int:
    async with sessions() as session:
        async with session.begin():
            row = (
                await session.execute(
                    text(
                        "SELECT id,topic,payload,attempts FROM outbox "
                        "WHERE status='pending' AND next_attempt_at <= now() "
                        "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
                    )
                )
            ).mappings().first()
            if row is None:
                return 0
            await session.execute(
                text("UPDATE outbox SET status='processing' WHERE id=:id"), {"id": row["id"]}
            )
    try:
        await consumer(row["topic"], row["payload"])
    except Exception as error:
        async with sessions() as session:
            async with session.begin():
                attempts = row["attempts"] + 1
                if attempts >= max_attempts:
                    await session.execute(
                        text(
                            "INSERT INTO dead_letters(origin,payload,error_history,attempts) "
                            "VALUES ('outbox',:payload,CAST(:errors AS jsonb),:attempts)"
                        ),
                        {
                            "payload": json.dumps(row["payload"]),
                            "errors": json.dumps([str(error)]),
                            "attempts": attempts,
                        },
                    )
                    status = "dead_lettered"
                else:
                    delay = min(60, 2**attempts) + random.random()
                    await session.execute(
                        text(
                            "UPDATE outbox SET status='pending',attempts=:attempts,"
                            "next_attempt_at=:next WHERE id=:id"
                        ),
                        {
                            "id": row["id"],
                            "attempts": attempts,
                            "next": datetime.now(UTC) + timedelta(seconds=delay),
                        },
                    )
                    status = "pending"
                if status == "dead_lettered":
                    await session.execute(
                        text("UPDATE outbox SET status=:status,attempts=:attempts WHERE id=:id"),
                        {"id": row["id"], "status": status, "attempts": attempts},
                    )
    else:
        async with sessions() as session:
            async with session.begin():
                await session.execute(
                    text("UPDATE outbox SET status='sent' WHERE id=:id"), {"id": row["id"]}
                )
    return 1
