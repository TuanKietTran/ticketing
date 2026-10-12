from datetime import UTC, datetime

import pytest

from ticketing.clock import FrozenClock
from ticketing.faults import FaultInjector, FaultPoint


def test_frozen_clock_is_injectable() -> None:
    clock = FrozenClock(datetime(2025, 1, 1, tzinfo=UTC))
    clock.advance(2.5)
    assert clock.now().isoformat() == "2025-01-01T00:00:02.500000+00:00"


def test_fault_injector_named_point() -> None:
    faults = FaultInjector()
    faults.arm(FaultPoint.AFTER_CHARGE)
    with pytest.raises(RuntimeError, match="after_charge"):
        faults.hit(FaultPoint.AFTER_CHARGE)
    faults.disarm(FaultPoint.AFTER_CHARGE)
    faults.hit(FaultPoint.AFTER_CHARGE)
