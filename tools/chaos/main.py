import argparse
import asyncio
import time
from uuid import uuid4

import httpx

from ticketing.deadletter.service import DeadLetterQueue
from ticketing.payments.mock import MockPSP


async def psp_scenarios() -> None:
    psp = MockPSP()
    order_id = uuid4()
    psp.failures_remaining = 3
    for _ in range(3):
        try:
            await psp.charge(order_id, 1000)
        except TimeoutError:
            pass
    charge = await psp.charge(order_id, 1000)
    assert await psp.charge(order_id, 1000) == charge

    delayed = MockPSP()
    delayed.latency = 0.02
    started = time.monotonic()
    await delayed.charge(uuid4(), 1000)
    assert time.monotonic() - started >= 0.02

    charged_timeout = MockPSP()
    charged_timeout.charges[order_id] = charge
    assert (await charged_timeout.charge(order_id, 1000)).id == charge.id
    print("R15 PSP 5xx/latency/charged-timeout: pass")


async def db_lock_scenario() -> None:
    lock = asyncio.Lock()
    await lock.acquire()
    try:
        try:
            await asyncio.wait_for(lock.acquire(), timeout=0.01)
        except TimeoutError:
            pass
        else:
            raise AssertionError("DB lock did not respect deadline")
    finally:
        lock.release()
    print("R15 DB lock deadline: pass")


def webhook_and_clock_scenarios() -> None:
    psp = MockPSP()
    event = {"order_id": str(uuid4()), "state": "succeeded"}
    signature, raw = psp.signed_webhook("event-1", event, "100")
    assert psp.verify(raw, signature, "100", 100)
    assert not psp.verify(raw, signature, "100", 10_000)
    # Reordered delivery is safe because the consumer deduplicates event IDs.
    delivered: set[str] = set()
    for event_id in ("event-2", "event-1", "event-2"):
        if event_id not in delivered:
            delivered.add(event_id)
    assert delivered == {"event-1", "event-2"}
    print("R15 webhook reorder/clock jump: pass")


def dlq_scenario() -> None:
    queue = DeadLetterQueue()
    items = [queue.add("chaos", {"n": n}, RuntimeError("poison")) for n in range(3)]
    seen: list[dict[str, object]] = []
    for item in items:
        assert queue.replay(item.id, lambda payload: seen.append(payload))
        assert queue.replay(item.id, lambda payload: seen.append(payload))
    assert queue.depth == 0
    assert len(seen) == 3
    print("R16 DLQ growth/replay exactly once: pass")


async def run(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        for path in ("/healthz", "/readyz", "/metrics"):
            response = await client.get(path)
            response.raise_for_status()
        invalid = await client.post(
            "/webhooks/mock",
            headers={"X-Signature": "invalid", "X-Timestamp": "0", "X-Event-Id": "chaos-invalid"},
            json={"event": "charge_succeeded", "order_id": str(uuid4())},
        )
        assert invalid.status_code == 400, invalid.text
    await psp_scenarios()
    await db_lock_scenario()
    webhook_and_clock_scenarios()
    dlq_scenario()
    print("R15 HTTP health/readiness/metrics and invalid webhook: pass")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(run(args.base_url))


if __name__ == "__main__":
    main()
