from ticketing.faults import FaultInjector, FaultPoint


def test_R15_chaos_fault_points_are_scriptable() -> None:
    faults = FaultInjector()
    for point in FaultPoint:
        faults.arm(point)
        faults.disarm(point)
    assert not faults._armed  # noqa: SLF001
