import argparse
import asyncio
import random
import statistics
import time
from uuid import UUID, uuid4

import httpx

from tools.invariants.main import check_database


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    key: str,
    payload: dict[str, object] | None = None,
) -> httpx.Response | None:
    for attempt in range(3):
        try:
            response = await client.request(
                method,
                path,
                headers={"Idempotency-Key": key},
                json=payload,
            )
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
        except httpx.HTTPError:
            response = None
        await asyncio.sleep(random.uniform(0.01, 0.1) * (attempt + 1))
    return response


async def buyer(
    client: httpx.AsyncClient,
    base_url: str,
    event_id: UUID,
    buyer_id: UUID,
    gate: asyncio.Semaphore,
) -> float:
    started = time.perf_counter()
    async with gate:
        hold_key = str(uuid4())
        response = await request_with_retries(
            client,
            "POST",
            f"{base_url}/events/{event_id}/holds",
            hold_key,
            {"buyer_id": str(buyer_id), "quantity": 1},
        )
        if response is not None and response.status_code == 201:
            hold_id = response.json()["hold_id"]
            order = await request_with_retries(
                client,
                "POST",
                f"{base_url}/holds/{hold_id}/checkout",
                str(uuid4()),
            )
            if order is not None and order.status_code == 201:
                await request_with_retries(
                    client,
                    "POST",
                    f"{base_url}/orders/{order.json()['order_id']}/pay",
                    str(uuid4()),
                )
    return (time.perf_counter() - started) * 1000


async def run(base_url: str, buyers: int, capacity: int) -> dict[str, float | int | str]:
    event_id = uuid4()
    gate = asyncio.Semaphore(100)
    limits = httpx.Limits(max_connections=300, max_keepalive_connections=100)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        await request_with_retries(
            client,
            "POST",
            f"{base_url}/admin/events/{event_id}/inventory",
            f"seed-{event_id}",
            {"capacity": capacity},
        )
        latencies = await asyncio.gather(
            *(buyer(client, base_url, event_id, uuid4(), gate) for _ in range(buyers))
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
