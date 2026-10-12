from datetime import UTC, datetime

from ticketing.clock import FrozenClock


def test_R13_injectable_clock() -> None:
    clock = FrozenClock(datetime(2025, 1, 1, tzinfo=UTC))
    assert clock.now().year == 2025
