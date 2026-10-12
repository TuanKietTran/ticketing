from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from ticketing.inventory.service import Inventory, SoldOut


def test_concurrent_holds_never_oversell() -> None:
    inventory = Inventory()
    event, buyer = uuid4(), uuid4()
    inventory.add_section(event, 10)
    now = datetime.now(UTC)
    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(lambda _: _hold(inventory, event, buyer, now), range(100)))
    assert sum(results) == 10
    snapshot = inventory.snapshot(event)
    assert snapshot.sold + snapshot.held <= snapshot.capacity


def _hold(inventory: Inventory, event, buyer, now) -> int:  # type: ignore[no-untyped-def]
    try:
        inventory.hold(event, buyer, 1, now)
        return 1
    except SoldOut:
        return 0
