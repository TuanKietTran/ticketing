import argparse
import asyncio
import random
import re
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
    endpoint: str = "other",
    metrics: dict[str, list[float] | int] | None = None,
) -> httpx.Response | None:
    for attempt in range(3):
        started = time.perf_counter()
        try:
            response = await client.request(
                method,
                path,
                headers={"Idempotency-Key": key},
                json=payload,
            )
            elapsed = (time.perf_counter() - started) * 1000
            if metrics is not None:
                metrics.setdefault(endpoint, []).append(elapsed)
                metrics["request_count"] = int(metrics.get("request_count", 0)) + 1
                if attempt:
                    metrics["retry_count"] = int(metrics.get("retry_count", 0)) + 1
                if response.status_code in {429, 503}:
                    metrics["shed_count"] = int(metrics.get("shed_count", 0)) + 1
                elif response.status_code == 409:
                    metrics["expected_terminal_count"] = int(
                        metrics.get("expected_terminal_count", 0)
                    ) + 1
                elif response.status_code >= 400:
                    metrics["error_count"] = int(metrics.get("error_count", 0)) + 1
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
        except httpx.HTTPError:
            if metrics is not None:
                metrics["error_count"] = int(metrics.get("error_count", 0)) + 1
                metrics["request_count"] = int(metrics.get("request_count", 0)) + 1
            response = None
        await asyncio.sleep(random.uniform(0.01, 0.1) * (attempt + 1))
    return response


async def buyer(
    client: httpx.AsyncClient,
    base_url: str,
    event_id: UUID,
    buyer_id: UUID,
    gate: asyncio.Semaphore,
    metrics: dict[str, list[float] | int],
    start_delay: float = 0.0,
) -> float:
    if start_delay:
        await asyncio.sleep(start_delay)
    started = time.perf_counter()
    async with gate:
        # Sample browse independently so the 10k write path does not turn a
        # read-only cache probe into an artificial second hot-path workload.
        if buyer_id.int % 100 == 0:
            await request_with_retries(
                client,
                "GET",
                f"{base_url}/events/{event_id}",
                f"browse-{buyer_id}",
                endpoint="browse",
                metrics=metrics,
            )
        hold_key = str(uuid4())
        response = await request_with_retries(
            client,
            "POST",
            f"{base_url}/events/{event_id}/holds",
            hold_key,
            {"buyer_id": str(buyer_id), "quantity": 1},
            endpoint="hold",
            metrics=metrics,
        )
        if response is not None and response.status_code == 201:
            hold_id = response.json()["hold_id"]
            order = await request_with_retries(
                client,
                "POST",
                f"{base_url}/holds/{hold_id}/checkout",
                str(uuid4()),
                endpoint="checkout",
                metrics=metrics,
            )
            if order is not None and order.status_code == 201:
                await request_with_retries(
                    client,
                    "POST",
                    f"{base_url}/orders/{order.json()['order_id']}/pay",
                    str(uuid4()),
                    endpoint="pay",
                    metrics=metrics,
                )
    return (time.perf_counter() - started) * 1000


async def scrape_server_metrics(
    client: httpx.AsyncClient, base_url: str
) -> dict[str, float | int]:
    response = await client.get(f"{base_url}/metrics")
    response.raise_for_status()
    buckets: dict[str, list[tuple[float, int]]] = {}
    counts: dict[str, int] = {}
    for line in response.text.splitlines():
        match = re.match(
            r'ticketing_request_duration_seconds_bucket\{endpoint="([^"]+)",le="([^"]+)"\} (\d+)',
            line,
        )
        if not match:
            continue
        endpoint, bound, count = match.groups()
        if bound == "+Inf":
            counts[endpoint] = int(count)
        else:
            buckets.setdefault(endpoint, []).append((float(bound), int(count)))
    result: dict[str, float | int] = {}
    for endpoint, values in buckets.items():
        total = counts.get(endpoint, 0)
        target = total * 0.99
        bound = next((bound for bound, count in values if count >= target), 0.0)
        result[f"server_{endpoint}_count"] = total
        result[f"server_{endpoint}_p99_bucket_ms"] = bound * 1000
    return result


async def run(
    base_url: str,
    buyers: int,
    capacity: int,
    concurrency: int = 100,
    ramp_seconds: float = 0.0,
) -> dict[str, float | int | str]:
    event_id = uuid4()
    gate = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=300, max_keepalive_connections=100)
    metrics: dict[str, list[float] | int] = {}
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        await request_with_retries(
            client,
            "POST",
            f"{base_url}/admin/events/{event_id}/inventory",
            f"seed-{event_id}",
            {"capacity": capacity},
        )
        latencies = await asyncio.gather(
            *(
                buyer(
                    client,
                    base_url,
                    event_id,
                    uuid4(),
                    gate,
                    metrics,
                    (index / max(1, buyers - 1)) * ramp_seconds,
                )
                for index in range(buyers)
            )
        )
        server_metrics = await scrape_server_metrics(client, base_url)
    ordered = sorted(latencies)
    invariants = await check_database(event_id)

    def percentile(values: list[float], percentile_rank: float) -> float:
        if not values:
            return 0.0
        return sorted(values)[max(0, int(len(values) * percentile_rank) - 1)]

    endpoint_stats: dict[str, float] = {}
    for endpoint in ("browse", "hold", "pay", "poll"):
        values = metrics.get(endpoint, [])
        assert isinstance(values, list)
        endpoint_stats[f"{endpoint}_p50_ms"] = percentile(values, 0.50)
        endpoint_stats[f"{endpoint}_p99_ms"] = percentile(values, 0.99)
    requests = int(metrics.get("request_count", 0))
    errors = int(metrics.get("error_count", 0))
    return {
        "event_id": str(event_id),
        "buyers": buyers,
        "capacity": capacity,
        "completed": len(latencies),
        "p99_ms": ordered[max(0, int(len(ordered) * 0.99) - 1)],
        "mean_ms": statistics.mean(latencies),
        **endpoint_stats,
        **server_metrics,
        "request_count": requests,
        "retry_count": int(metrics.get("retry_count", 0)),
        "shed_429_503": int(metrics.get("shed_count", 0)),
        "expected_terminal_409": int(metrics.get("expected_terminal_count", 0)),
        "error_count_excluding_shedding": errors,
        "error_rate_excluding_shedding": errors / requests if requests else 0.0,
        **invariants,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--buyers", type=int, default=10_000)
    parser.add_argument("--capacity", type=int, default=1_000)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--ramp-seconds", type=float, default=0.0)
    args = parser.parse_args()
    print(
        asyncio.run(
            run(
                args.base_url,
                args.buyers,
                args.capacity,
                args.concurrency,
                args.ramp_seconds,
            )
        )
    )


if __name__ == "__main__":
    main()
