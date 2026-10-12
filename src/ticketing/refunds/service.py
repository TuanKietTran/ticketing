from dataclasses import dataclass
from threading import Lock
from uuid import UUID


@dataclass(frozen=True)
class Refund:
    id: UUID
    order_id: UUID
    amount_minor: int


class Refunds:
    def __init__(self) -> None:
        self._lock = Lock()
        self._refunds: dict[tuple[UUID, int], Refund] = {}

    def refund(self, refund_id: UUID, order_id: UUID, amount_minor: int) -> Refund:
        with self._lock:
            key = (order_id, amount_minor)
            if key not in self._refunds:
                self._refunds[key] = Refund(refund_id, order_id, amount_minor)
            return self._refunds[key]
