import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ChargeState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class Charge:
    id: str
    order_id: UUID
    amount_minor: int
    state: ChargeState


class MockPSP:
    def __init__(self, secret: str = "psp-secret") -> None:
        self.secret = secret.encode()
        self.charges: dict[UUID, Charge] = {}
        self.webhooks: list[dict[str, object]] = []
        self.failures_remaining = 0
        self.latency = 0.0

    async def charge(self, order_id: UUID, amount_minor: int) -> Charge:
        if order_id in self.charges:
            return self.charges[order_id]
        if self.latency:
            await asyncio.sleep(self.latency)
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise TimeoutError("mock PSP failure")
        charge = Charge(f"ch_{order_id}", order_id, amount_minor, ChargeState.SUCCEEDED)
        self.charges[order_id] = charge
        return charge

    def signed_webhook(
        self, event_id: str, payload: dict[str, object], timestamp: str
    ) -> tuple[str, str]:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(self.secret, f"{timestamp}.{raw}".encode(), hashlib.sha256).hexdigest()
        return signature, raw

    def verify(
        self, raw: str, signature: str, timestamp: str, now: int, tolerance: int = 300
    ) -> bool:
        try:
            if abs(now - int(timestamp)) > tolerance:
                return False
        except ValueError:
            return False
        expected = hmac.new(self.secret, f"{timestamp}.{raw}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
