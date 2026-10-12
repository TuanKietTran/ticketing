import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_idempotent[T](
    operation: Callable[[], Awaitable[T]],
    attempts: int = 3,
    deadline_seconds: float = 5,
    budget: list[int] | None = None,
) -> T:
    started = time.monotonic()
    last_error: Exception | None = None
    for attempt in range(attempts):
        if budget is not None:
            if not budget or budget[0] <= 0:
                break
            budget[0] -= 1
        try:
            return await asyncio.wait_for(
                operation(), timeout=max(0.001, deadline_seconds - (time.monotonic() - started))
            )
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                delay = random.uniform(0, min(1.0, 2**attempt))
                if time.monotonic() + delay >= started + deadline_seconds:
                    break
                await asyncio.sleep(delay)
    if last_error is None:
        raise RuntimeError("retry budget exhausted")
    raise last_error
