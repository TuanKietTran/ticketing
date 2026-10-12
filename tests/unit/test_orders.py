from uuid import uuid4

import pytest

from ticketing.orders.service import IdempotencyStore, OrderState, new_order


def test_order_transition_is_centralized() -> None:
    order = new_order(uuid4(), 1)
    order.transition(OrderState.AWAITING_PAYMENT, "hold checkout")
    order.transition(OrderState.PAID, "charge succeeded")
    assert order.state is OrderState.PAID
    with pytest.raises(ValueError):
        order.transition(OrderState.PENDING, "invalid")


def test_idempotency_replays_and_rejects_body_change() -> None:
    store = IdempotencyStore()
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        return type("Result", (), {"status_code": 201, "body": {"ok": True}})()

    first = store.execute("buyer", "k", b"{}", operation)
    second = store.execute("buyer", "k", b"{}", operation)
    assert first == second
    assert calls == 1
    with pytest.raises(ValueError):
        store.execute("buyer", "k", b"{\"x\":1}", operation)
