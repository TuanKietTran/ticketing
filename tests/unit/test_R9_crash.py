import pytest

from ticketing.faults import FaultInjector, FaultPoint


def test_R9_named_crash_point_is_recoverable_hook() -> None:
    faults = FaultInjector()
    faults.arm(FaultPoint.AFTER_HOLD)
    with pytest.raises(RuntimeError):
        faults.hit(FaultPoint.AFTER_HOLD)
    faults.disarm(FaultPoint.AFTER_HOLD)
    faults.hit(FaultPoint.AFTER_HOLD)
