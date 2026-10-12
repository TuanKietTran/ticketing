from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from threading import Lock
from uuid import UUID, uuid4


class OrderState(StrEnum):
    PENDING = "pending"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    TICKETED = "ticketed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

_ALLOWED: dict[OrderState, set[OrderState]] = {
    OrderState.PENDING: {
        OrderState.AWAITING_PAYMENT,
        OrderState.FAILED,
        OrderState.EXPIRED,
        OrderState.CANCELLED,
    },
    OrderState.AWAITING_PAYMENT: {
        OrderState.PAID,
        OrderState.FAILED,
        OrderState.EXPIRED,
        OrderState.CANCELLED,
    },
    OrderState.PAID: {OrderState.TICKETED, OrderState.REFUNDED, OrderState.CANCELLED},
    OrderState.TICKETED: {OrderState.REFUNDED, OrderState.CANCELLED},
    OrderState.CANCELLED: {OrderState.REFUNDED},
    OrderState.FAILED: {OrderState.PENDING},
    OrderState.EXPIRED: {OrderState.PENDING},
    OrderState.REFUNDED: set(),
}


@dataclass
class Order:
    id: UUID
    buyer_id: UUID
    quantity: int
    state: OrderState = OrderState.PENDING
    events: list[tuple[OrderState, OrderState, str]] = field(default_factory=list)

    def transition(self, target: OrderState, reason: str) -> None:
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"invalid transition {self.state} -> {target}")
        old = self.state
        self.state = target
        self.events.append((old, target, reason))


@dataclass(frozen=True)
class IdempotencyResult:
    status_code: int
    body: object


class IdempotencyStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._values: dict[tuple[str, str], tuple[str, IdempotencyResult]] = {}

    def execute(self, actor: str, key: str, body: bytes, operation: object) -> IdempotencyResult:
        digest = sha256(body).hexdigest()
        identity = (actor, key)
        with self._lock:
            stored = self._values.get(identity)
            if stored:
                if stored[0] != digest:
                    raise ValueError("idempotency key reused with a different body")
                return stored[1]
            result = operation()  # type: ignore[operator]
            self._values[identity] = (digest, result)
            return result


def new_order(buyer_id: UUID, quantity: int) -> Order:
    return Order(uuid4(), buyer_id, quantity)
