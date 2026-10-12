from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class InventoryClaim:
    event_id: UUID
    quantity: int
    hold_id: UUID


class Store(Protocol):
    async def claim_inventory(self, claim: InventoryClaim) -> bool: ...
    async def release_inventory(self, hold_id: UUID) -> bool: ...
