from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID, uuid4


@dataclass
class DeadLetter:
    id: UUID
    origin: str
    payload: dict[str, object]
    error_history: list[str] = field(default_factory=list)
    attempts: int = 0
    status: str = "open"
    discard_reason: str | None = None


class DeadLetterQueue:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[UUID, DeadLetter] = {}
        self._replayed: set[UUID] = set()

    def add(self, origin: str, payload: dict[str, object], error: Exception) -> DeadLetter:
        with self._lock:
            item = DeadLetter(uuid4(), origin, payload, [str(error)], 1)
            self._items[item.id] = item
            return item

    def list(self) -> list[DeadLetter]:
        with self._lock:
            return list(self._items.values())

    def replay(self, item_id: UUID, consumer) -> bool:  # type: ignore[no-untyped-def]
        with self._lock:
            if item_id in self._replayed:
                return True
            item = self._items[item_id]
        consumer(item.payload)
        with self._lock:
            self._replayed.add(item_id)
            item.status = "replayed"
        return True

    def discard(self, item_id: UUID, reason: str) -> None:
        with self._lock:
            item = self._items[item_id]
            item.status = "discarded"
            item.discard_reason = reason

    @property
    def depth(self) -> int:
        return sum(item.status == "open" for item in self._items.values())
