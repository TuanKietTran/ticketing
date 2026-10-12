import pytest

from ticketing.retry import retry_idempotent


@pytest.mark.asyncio
async def test_R4_retry_budget_caps_idempotent_retries() -> None:
    calls = 0
    budget = [2]

    async def failing() -> None:
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary")

    with pytest.raises(TimeoutError):
        await retry_idempotent(failing, attempts=5, deadline_seconds=1, budget=budget)
    assert calls == 2
    assert budget == [0]
