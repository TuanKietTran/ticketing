import asyncio

import pytest

from ticketing.resilience import BreakerState, Bulkhead, CircuitBreaker


def test_R6_circuit_breaker_opens_after_failures() -> None:
    breaker = CircuitBreaker(failures=2, reset_seconds=30)
    breaker.failure()
    breaker.failure()
    assert breaker.state is BreakerState.OPEN
    with pytest.raises(RuntimeError):
        breaker.before_call()


@pytest.mark.asyncio
async def test_R6_bulkhead_limits_dependency_concurrency() -> None:
    bulkhead = Bulkhead(2)
    active = 0
    maximum = 0
    lock = asyncio.Lock()

    async def operation() -> None:
        nonlocal active, maximum
        async with lock:
            active += 1
            maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        async with lock:
            active -= 1

    await asyncio.gather(*(bulkhead.run(operation) for _ in range(10)))
    assert maximum == 2
