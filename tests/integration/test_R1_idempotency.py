import asyncio
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ticketing.api.idempotency import IdempotencyMiddleware


@pytest.mark.asyncio
async def test_R1_replay_and_body_mismatch_postgres() -> None:
    engine = create_async_engine("postgresql+asyncpg://ticketing:ticketing@localhost:5432/ticketing")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM idempotency_keys"))
    calls = 0
    inner = FastAPI()

    @inner.post("/mutate")
    async def mutate(payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"call": calls, "payload": payload}

    wrapped = IdempotencyMiddleware(inner, factory)
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Idempotency-Key": "r1", "X-Actor-ID": str(uuid4())}
        first = await client.post("/mutate", headers=headers, json={"x": 1})
        replay = await client.post("/mutate", headers=headers, json={"x": 1})
        mismatch = await client.post("/mutate", headers=headers, json={"x": 2})
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert mismatch.status_code == 422
    assert calls == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_R3_concurrent_retry_storm_executes_once_postgres() -> None:
    engine = create_async_engine("postgresql+asyncpg://ticketing:ticketing@localhost:5432/ticketing")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM idempotency_keys"))
    calls = 0
    inner = FastAPI()

    @inner.post("/mutate")
    async def mutate() -> dict[str, bool]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return {"ok": True}

    wrapped = IdempotencyMiddleware(inner, factory)
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Idempotency-Key": "storm", "X-Actor-ID": str(uuid4())}
        responses = await asyncio.gather(
            *(client.post("/mutate", headers=headers, json={}) for _ in range(20))
        )
    assert {response.status_code for response in responses} == {200}
    assert all(response.json() == {"ok": True} for response in responses)
    assert calls == 1
    await engine.dispose()
