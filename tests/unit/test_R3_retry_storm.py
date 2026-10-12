import asyncio

import pytest

from ticketing.retry import retry_idempotent


@pytest.mark.asyncio
async def test_R3_retry_storm_timeout_after_commit_is_idempotent() -> None:
    committed: dict[str, str] = {}
    attempts = 0

    async def charge_once() -> str:
        nonlocal attempts
        attempts += 1
        if "charge" not in committed:
            committed["charge"] = "charge-1"
            raise TimeoutError("response lost after commit")
        return committed["charge"]

    results = [
        await retry_idempotent(charge_once, attempts=3, deadline_seconds=2)
        for _ in range(3)
    ]
    assert results == ["charge-1"] * 3
    assert committed == {"charge": "charge-1"}
    assert attempts == 4
    await asyncio.sleep(0)
