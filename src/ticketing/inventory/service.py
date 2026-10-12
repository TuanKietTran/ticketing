from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4


class InventoryError(Exception):
    """Base inventory failure."""


class SoldOut(InventoryError):
    pass


@dataclass
class Hold:
    id: UUID
    event_id: UUID
    buyer_id: UUID
    quantity: int
    expires_at: datetime
    active: bool = True


@dataclass
class GeneralAdmission:
    capacity: int
    held: int = 0
    sold: int = 0


class Inventory:
    """Concurrency-safe reference implementation of guarded inventory updates."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._stock: dict[UUID, GeneralAdmission] = {}
        self._holds: dict[UUID, Hold] = {}

    def add_section(self, event_id: UUID, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("capacity must be non-negative")
        with self._lock:
            self._stock[event_id] = GeneralAdmission(capacity=capacity)

    def hold(
        self, event_id: UUID, buyer_id: UUID, quantity: int, now: datetime, ttl: int = 600
    ) -> Hold:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        with self._lock:
            stock = self._stock[event_id]
            if stock.sold + stock.held + quantity > stock.capacity:
                raise SoldOut("inventory unavailable")
            stock.held += quantity
            hold = Hold(uuid4(), event_id, buyer_id, quantity, now + timedelta(seconds=ttl))
            self._holds[hold.id] = hold
            return hold

    def checkout(self, hold_id: UUID, now: datetime) -> int:
        with self._lock:
            hold = self._holds[hold_id]
            if not hold.active or hold.expires_at <= now:
                raise InventoryError("hold expired")
            stock = self._stock[hold.event_id]
            stock.held -= hold.quantity
            stock.sold += hold.quantity
            hold.active = False
            return hold.quantity

    def release_expired(self, now: datetime) -> int:
        released = 0
        with self._lock:
            for hold in self._holds.values():
                if hold.active and hold.expires_at <= now:
                    hold.active = False
                    self._stock[hold.event_id].held -= hold.quantity
                    released += hold.quantity
        return released

    def snapshot(self, event_id: UUID) -> GeneralAdmission:
        with self._lock:
            stock = self._stock[event_id]
            return GeneralAdmission(stock.capacity, stock.held, stock.sold)
