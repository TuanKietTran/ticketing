import argparse
import asyncio
import statistics
import time
from uuid import UUID, uuid4

import httpx

from tools.invariants.main import check_database


async def buyer(client: httpx.AsyncClient, base_url: str, event_id: UUID, buyer_id: UUID) -> float:
    started = time.perf_counter()
    key = str(uuid4())
    response = await client.post(
        f"{base_url}/events/{event_id}/holds",
        headers={"Idempotency-Key": key},
        json={"buyer_id": str(buyer_id), "quantity": 1},
    )
    if response.status_code == 201:
        hold_id = response.json()["hold_id"]
        order = await client.post(
            f"{base_url}/holds/{hold_id}/checkout", headers={"Idempotency-Key": str(uuid4())}
        )
        if order.status_code == 201:
            await client.post(
                f"{base_url}/orders/{order.json()['order_id']}/pay",
                headers={"Idempotency-Key": str(uuid4())},
            )
    return (time.perf_counter() - started) * 1000


async def run(base_url: str, buyers: int, capacity: int) -> dict[str, float | int]:
    event_id = uuid4()
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        await client.post(
            f"/admin/events/{event_id}/inventory",
            headers={"Idempotency-Key": f"seed-{event_id}"},
            json={"capacity": capacity},
        )
        latencies = await asyncio.gather(
            *(buyer(client, base_url, event_id, uuid4()) for _ in range(buyers))
        )
    ordered = sorted(latencies)
    invariants = await check_database(event_id)
    return {
        "event_id": str(event_id),
        "buyers": buyers,
        "capacity": capacity,
        "completed": len(latencies),
        "p99_ms": ordered[max(0, int(len(ordered) * 0.99) - 1)],
        "mean_ms": statistics.mean(latencies),
        **invariants,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--buyers", type=int, default=10_000)
    parser.add_argument("--capacity", type=int, default=1_000)
    args = parser.parse_args()
    print(asyncio.run(run(args.base_url, args.buyers, args.capacity)))


if __name__ == "__main__":
    main()
