from enum import StrEnum


class FaultPoint(StrEnum):
    AFTER_HOLD = "after_hold"
    AFTER_CHARGE = "after_charge"
    BEFORE_TICKETING = "before_ticketing"
    MID_REFUND = "mid_refund"


class FaultInjector:
    def __init__(self) -> None:
        self._armed: set[FaultPoint] = set()

    def arm(self, point: FaultPoint) -> None:
        self._armed.add(point)

    def disarm(self, point: FaultPoint) -> None:
        self._armed.discard(point)

    def hit(self, point: FaultPoint) -> None:
        if point in self._armed:
            raise RuntimeError(f"injected fault at {point}")
