from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Admission:
    token: UUID
    buyer_id: UUID
    expires_at: datetime


class WaitingRoom:
    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self._queue: deque[UUID] = deque()
        self._tokens: dict[UUID, Admission] = {}
        self._lock = Lock()

    def enqueue(self, buyer_id: UUID) -> int:
        with self._lock:
            already_admitted = any(a.buyer_id == buyer_id for a in self._tokens.values())
            if buyer_id not in self._queue and not already_admitted:
                self._queue.append(buyer_id)
            return list(self._queue).index(buyer_id) + 1 if buyer_id in self._queue else 0

    def admit(self, count: int, now: datetime | None = None, ttl: int = 60) -> list[Admission]:
        now = now or datetime.now(UTC)
        with self._lock:
            admitted = []
            for _ in range(min(count, len(self._queue))):
                buyer = self._queue.popleft()
                admission = Admission(uuid4(), buyer, now + timedelta(seconds=ttl))
                self._tokens[admission.token] = admission
                admitted.append(admission)
            return admitted

    def valid(self, token: UUID, now: datetime | None = None) -> bool:
        admission = self._tokens.get(token)
        return admission is not None and admission.expires_at > (now or datetime.now(UTC))
