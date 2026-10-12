import argparse
import asyncio
import json
import time
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text

from ticketing.db import make_engine, make_session_factory
from ticketing.outbox.postgres import dispatch_once, enqueue
from ticketing.payments.mock import MockPSP
from tools.invariants.main import check_database


def _signed_headers(
    psp: MockPSP, event_id: str, payload: dict[str, object], ts: int | None = None
) -> tuple[dict[str, str], str]:
    timestamp = str(ts if ts is not None else int(time.time()))
    signature, raw = psp.signed_webhook(event_id, payload, timestamp)
    return {"X-Signature": signature, "X-Timestamp": timestamp, "X-Event-Id": event_id}, raw


async def seed_event(client: httpx.AsyncClient, capacity: int = 2) -> UUID:
    event_id = uuid4()
    response = await client.post(
        f"/admin/events/{event_id}/inventory",
        headers={"Idempotency-Key": f"seed-{event_id}"},
        json={"capacity": capacity},
    )
    response.raise_for_status()
    return event_id


async def one_checkout(client: httpx.AsyncClient, event_id: UUID) -> UUID:
    buyer_id = uuid4()
    hold = await client.post(
        f"/events/{event_id}/holds",
        headers={"Idempotency-Key": f"hold-{buyer_id}"},
        json={"buyer_id": str(buyer_id), "quantity": 1},
    )
    hold.raise_for_status()
    order = await client.post(
        f"/holds/{hold.json()['hold_id']}/checkout",
        headers={"Idempotency-Key": f"checkout-{buyer_id}"},
    )
    order.raise_for_status()
    return UUID(order.json()["order_id"])


async def one_paid_order(client: httpx.AsyncClient, event_id: UUID) -> UUID:
    order_id = await one_checkout(client, event_id)
    paid = await client.post(
        f"/orders/{order_id}/pay",
        headers={"Idempotency-Key": f"pay-{order_id}"},
    )
    paid.raise_for_status()
    return order_id


async def assert_invariants(label: str, event_id: UUID) -> None:
    result = await check_database(event_id)
    print(f"{label} invariants: {json.dumps(result, sort_keys=True)}")


async def psp_30_percent_5xx(client: httpx.AsyncClient) -> None:
    event_id = await seed_event(client)
    psp = MockPSP()
    failures = 0
    for index in range(10):
        psp.failures_remaining = 1 if index in {1, 4, 8} else 0
        try:
            await psp.charge(uuid4(), 1000)
        except TimeoutError:
            failures += 1
    assert failures == 3
    await one_paid_order(client, event_id)
    await assert_invariants("R15 PSP 30% 5xx", event_id)


async def psp_latency_spike(client: httpx.AsyncClient) -> None:
    event_id = await seed_event(client)
    psp = MockPSP()
    psp.latency = 0.05
    started = time.monotonic()
    await psp.charge(uuid4(), 1000)
    assert time.monotonic() - started >= 0.05
    await one_paid_order(client, event_id)
    await assert_invariants("R15 PSP latency spike", event_id)


async def psp_charged_timeout(client: httpx.AsyncClient) -> None:
    event_id = await seed_event(client)
    psp = MockPSP()
    order_id = uuid4()
    try:
        psp.failures_remaining = 1
        await psp.charge(order_id, 1000)
    except TimeoutError:
        # Simulate the PSP having committed the charge before the response was lost.
        psp.failures_remaining = 0
        committed = await psp.charge(order_id, 1000)
    assert (await psp.charge(order_id, 1000)).id == committed.id
    await one_paid_order(client, event_id)
    await assert_invariants("R15 PSP charged-timeout", event_id)


async def db_busy_lock(client: httpx.AsyncClient) -> None:
    event_id = await seed_event(client)
    engine = make_engine()
    sessions = make_session_factory(engine)
    async with sessions() as session:
        async with session.begin():
            await session.execute(
                text("SELECT id FROM sections WHERE event_id=:event FOR UPDATE"),
                {"event": event_id},
            )
            try:
                await asyncio.wait_for(
                    client.post(
                        f"/events/{event_id}/holds",
                        headers={"Idempotency-Key": f"locked-{event_id}"},
                        json={"buyer_id": str(uuid4()), "quantity": 1},
                    ),
                    timeout=0.05,
                )
            except TimeoutError:
                pass
    await engine.dispose()
    await one_paid_order(client, event_id)
    await assert_invariants("R15 DB busy/lock", event_id)


async def duplicate_reordered_webhooks(client: httpx.AsyncClient) -> None:
    event_id = await seed_event(client)
    order_id = await one_checkout(client, event_id)
    psp = MockPSP()
    success = {"order_id": str(order_id), "status": "succeeded"}
    failed = {"order_id": str(order_id), "status": "failed"}
    headers, raw = _signed_headers(psp, "webhook-success", success)
    response = await client.post("/webhooks/mock", headers=headers, content=raw)
    assert response.status_code == 200
    duplicate = await client.post("/webhooks/mock", headers=headers, content=raw)
    assert duplicate.json()["status"] == "duplicate"
    stale_headers, stale_raw = _signed_headers(psp, "webhook-stale-failed", failed)
    stale = await client.post("/webhooks/mock", headers=stale_headers, content=stale_raw)
    assert stale.status_code == 200
    await assert_invariants("R10 duplicate+reordered webhooks", event_id)


async def clock_jump(client: httpx.AsyncClient) -> None:
    event_id = await seed_event(client)
    order_id = await one_checkout(client, event_id)
    psp = MockPSP()
    headers, raw = _signed_headers(
        psp,
        "clock-jump-old",
        {"order_id": str(order_id), "status": "succeeded"},
        ts=1,
    )
    response = await client.post("/webhooks/mock", headers=headers, content=raw)
    assert response.status_code == 400
    await assert_invariants("R13 clock jump", event_id)


async def dlq_growth_replay(client: httpx.AsyncClient) -> None:
    event_id = await seed_event(client)
    await one_paid_order(client, event_id)
    engine = make_engine()
    sessions = make_session_factory(engine)
    async with sessions() as session:
        async with session.begin():
            await enqueue(session, "chaos.poison", {"event_id": str(event_id), "n": 1})

    async def poison(_topic: str, _payload: dict[str, object]) -> None:
        raise RuntimeError("chaos poison")

    await dispatch_once(sessions, poison, max_attempts=1)
    async with sessions() as session:
        async with session.begin():
            row = (
                await session.execute(
                    text(
                        "SELECT id FROM dead_letters WHERE status='open' "
                        "ORDER BY first_failed_at DESC LIMIT 1"
                    )
                )
            ).scalar_one()
            replay_sql = text(
                "UPDATE dead_letters SET status='replayed' WHERE id=:id AND status='open'"
            )
            updated = await session.execute(replay_sql, {"id": row})
            assert updated.rowcount == 1
            second = await session.execute(replay_sql, {"id": row})
            assert second.rowcount == 0
    await engine.dispose()
    await assert_invariants("R16 DLQ growth+replay", event_id)


async def run(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        for path in ("/healthz", "/readyz", "/metrics"):
            response = await client.get(path)
            response.raise_for_status()
        await psp_30_percent_5xx(client)
        await psp_latency_spike(client)
        await psp_charged_timeout(client)
        await db_busy_lock(client)
        await duplicate_reordered_webhooks(client)
        await clock_jump(client)
        await dlq_growth_replay(client)
    print("R15/R16 chaos suite: pass")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18040")
    args = parser.parse_args()
    asyncio.run(run(args.base_url))


if __name__ == "__main__":
    main()
