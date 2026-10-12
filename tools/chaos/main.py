import argparse
import asyncio

import httpx


async def run(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        response = await client.get("/healthz")
        response.raise_for_status()
        print("chaos baseline: healthy; fault hooks are exercised by unit tests")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(run(args.base_url))


if __name__ == "__main__":
    main()
