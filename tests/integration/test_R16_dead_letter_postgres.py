from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ticketing.outbox.postgres import dispatch_once, enqueue


@pytest.mark.asyncio
async def test_R16_poison_outbox_flows_to_postgres_dead_letter() -> None:
    engine = create_async_engine("postgresql+asyncpg://ticketing:ticketing@localhost:5432/ticketing")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE outbox,dead_letters"))
    async with factory() as session:
        async with session.begin():
            await enqueue(session, "poison", {"id": str(uuid4())})

    async def poison(topic: str, payload: dict[str, object]) -> None:
        raise RuntimeError("dependency flapping")

    await dispatch_once(factory, poison, max_attempts=2)
    async with factory() as session:
        async with session.begin():
            await session.execute(text("UPDATE outbox SET next_attempt_at=now()"))
    await dispatch_once(factory, poison, max_attempts=2)
    async with factory() as session:
        depth = (
            await session.execute(text("SELECT count(*) FROM dead_letters WHERE origin='outbox'"))
        ).scalar_one()
        status = (await session.execute(text("SELECT status FROM outbox"))).scalar_one()
    assert depth == 1
    assert status == "dead_lettered"
    await engine.dispose()
