import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

from ticketing.deadletter import DeadLetterQueue


@dataclass
class OutboxMessage:
    id: UUID
    topic: str
    payload: dict[str, object]
    attempts: int = 0
    next_attempt_at: datetime = datetime.now(UTC)
    status: str = "pending"


class Outbox:
    def __init__(self, dead_letters: DeadLetterQueue, max_attempts: int = 3) -> None:
        self._lock = Lock()
        self._messages: dict[UUID, OutboxMessage] = {}
        self.dead_letters = dead_letters
        self.max_attempts = max_attempts

    def append(self, topic: str, payload: dict[str, object]) -> UUID:
        message = OutboxMessage(uuid4(), topic, payload)
        with self._lock:
            self._messages[message.id] = message
        return message.id

    def dispatch(self, consumer, now: datetime | None = None) -> None:  # type: ignore[no-untyped-def]
        now = now or datetime.now(UTC)
        for message in list(self._messages.values()):
            if message.status != "pending" or message.next_attempt_at > now:
                continue
            try:
                consumer(message.topic, message.payload)
            except Exception as error:
                message.attempts += 1
                if message.attempts >= self.max_attempts:
                    self.dead_letters.add("outbox", message.payload, error)
                    message.status = "dead_lettered"
                else:
                    delay = min(60, 2**message.attempts) + random.random()
                    message.next_attempt_at = now + timedelta(seconds=delay)
            else:
                message.status = "sent"

    @property
    def pending(self) -> int:
        return sum(message.status == "pending" for message in self._messages.values())
