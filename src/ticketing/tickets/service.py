import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from threading import Lock
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Ticket:
    id: UUID
    order_id: UUID
    payload: str


class TicketService:
    def __init__(self, signing_key: str) -> None:
        self._key = signing_key.encode()
        self._lock = Lock()
        self._by_order: dict[UUID, tuple[Ticket, ...]] = {}
        self._used: set[UUID] = set()

    def issue_once(self, order_id: UUID, quantity: int) -> tuple[Ticket, ...]:
        with self._lock:
            if order_id in self._by_order:
                return self._by_order[order_id]
            tickets = tuple(self._make(order_id) for _ in range(quantity))
            self._by_order[order_id] = tickets
            return tickets

    def _make(self, order_id: UUID) -> Ticket:
        ticket_id = uuid4()
        body = {"ticket_id": str(ticket_id), "order_id": str(order_id)}
        encoded = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True).encode()).decode()
        signature = hmac.new(self._key, encoded.encode(), hashlib.sha256).hexdigest()
        return Ticket(ticket_id, order_id, f"{encoded}.{signature}")

    def verify(self, ticket: Ticket) -> bool:
        encoded, signature = ticket.payload.rsplit(".", 1)
        expected = hmac.new(self._key, encoded.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def scan(self, ticket: Ticket) -> bool:
        if not self.verify(ticket):
            return False
        with self._lock:
            if ticket.id in self._used:
                return False
            self._used.add(ticket.id)
            return True
