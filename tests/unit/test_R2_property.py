from datetime import UTC, datetime
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from ticketing.inventory.service import Inventory, SoldOut


@given(
    capacity=st.integers(min_value=0, max_value=25),
    requests=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=30)
def test_R2_property_inventory_never_oversells(capacity: int, requests: int) -> None:
    inventory = Inventory()
    event, buyer = uuid4(), uuid4()
    inventory.add_section(event, capacity)
    now = datetime.now(UTC)
    successes = 0
    for _ in range(requests):
        try:
            inventory.hold(event, buyer, 1, now)
            successes += 1
        except SoldOut:
            pass
    snapshot = inventory.snapshot(event)
    assert successes <= capacity
    assert snapshot.sold + snapshot.held <= capacity
