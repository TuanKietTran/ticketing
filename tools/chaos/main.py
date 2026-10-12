import argparse
import asyncio

import httpx


async def run(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        health = await client.get("/healthz")
        health.raise_for_status()
        print("R15 health: pass")

        ready = await client.get("/readyz")
        ready.raise_for_status()
        print("R15 readiness: pass")

        invalid_webhook = await client.post(
            "/webhooks/mock",
            headers={"X-Signature": "invalid", "X-Timestamp": "0", "X-Event-Id": "chaos-invalid"},
            json={"event": "charge_succeeded", "order_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert invalid_webhook.status_code == 400, invalid_webhook.text
        print("R15 invalid webhook rejection: pass")

        metrics = await client.get("/metrics")
        metrics.raise_for_status()
        print("R15 metrics availability: pass")

        print(
            "R15 process-kill and dependency-fault behavior: "
            "exercised by worker-kill run and R15 tests"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(run(args.base_url))


if __name__ == "__main__":
    main()
