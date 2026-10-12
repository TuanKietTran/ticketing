from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    def __init__(self, value: datetime) -> None:
        self.value = value.astimezone(UTC)

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        from datetime import timedelta
        self.value += timedelta(seconds=seconds)
