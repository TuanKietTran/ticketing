import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, failures: int = 5, reset_seconds: float = 10) -> None:
        self.failures = failures
        self.reset_seconds = reset_seconds
        self.consecutive_failures = 0
        self.opened_at = 0.0
        self.state = BreakerState.CLOSED

    def before_call(self) -> None:
        if self.state is BreakerState.OPEN:
            if time.monotonic() - self.opened_at < self.reset_seconds:
                raise RuntimeError("circuit open")
            self.state = BreakerState.HALF_OPEN

    def success(self) -> None:
        self.consecutive_failures = 0
        self.state = BreakerState.CLOSED

    def failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failures:
            self.opened_at = time.monotonic()
            self.state = BreakerState.OPEN


class Bulkhead:
    def __init__(self, concurrency: int) -> None:
        self._semaphore = asyncio.Semaphore(concurrency)

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        async with self._semaphore:
            return await operation()
