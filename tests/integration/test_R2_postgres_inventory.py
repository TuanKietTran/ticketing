import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ticketing.inventory.postgres import claim_general_admission, release_expired


@pytest.mark.asyncio
async def test_R2_no_oversell_postgres_200_parallel_holds() -> None:
    engine = create_async_engine(
        "postgresql+asyncpg://ticketing:ticketing@localhost:5432/ticketing",
        pool_size=20,
        max_overflow=0,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    organizer, event, section = uuid4(), uuid4(), uuid4()
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE organizers CASCADE"))
        await connection.execute(
            text("INSERT INTO organizers(id,name,api_key_hash) VALUES (:id,'race','hash')"),
            {"id": organizer},
        )
        now = datetime.now(UTC)
        await connection.execute(
            text(
                "INSERT INTO events(id,organizer_id,name,sale_opens_at,sale_closes_at) "
                "VALUES (:id,:org,'race',:open,:close)"
            ),
            {
                "id": event,
                "org": organizer,
                "open": now - timedelta(hours=1),
                "close": now + timedelta(hours=1),
            },
        )
        await connection.execute(
            text(
                "INSERT INTO sections(id,event_id,name,mode,capacity) "
                "VALUES (:id,:event,'GA','general_admission',10)"
            ),
            {"id": section, "event": event},
        )

    async def attempt(number: int) -> bool:
        async with factory() as session:
            async with session.begin():
                result = await claim_general_admission(
                    session,
                    event,
                    section,
                    uuid4(),
                    f"race-{number}",
                    1,
                    datetime.now(UTC) + timedelta(minutes=10),
                )
                return result is not None

    results = await asyncio.gather(*(attempt(number) for number in range(200)))
    async with factory() as session:
        values = (
            await session.execute(
                text("SELECT capacity, held, sold FROM sections WHERE id=:id"), {"id": section}
            )
        ).one()
    assert sum(results) == 10
    assert values.held + values.sold <= values.capacity
    async with factory() as session:
        async with session.begin():
            released = await release_expired(session, datetime.now(UTC) + timedelta(hours=1))
    assert released == 10
    await engine.dispose()
