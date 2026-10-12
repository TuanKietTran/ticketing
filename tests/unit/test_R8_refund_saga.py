from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from ticketing.orders.service import OrderState, new_order
from ticketing.tickets.service import TicketService


def test_R8_refund_saga_voids_ticket_and_rejects_replay() -> None:
    order = new_order(uuid4(), 1)
    order.transition(OrderState.AWAITING_PAYMENT, "checkout")
    order.transition(OrderState.PAID, "charge")
    order.transition(OrderState.TICKETED, "issue")
    order.transition(OrderState.REFUNDED, "refund")
    assert order.state is OrderState.REFUNDED
    with pytest.raises(ValueError):
        order.transition(OrderState.TICKETED, "replay")


def test_R8_transfer_void_checkin_double_scan_race() -> None:
    service = TicketService("secret")
    ticket = service.issue_once(uuid4(), 1)[0]
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: service.scan(ticket), range(16)))
    assert sum(results) == 1
    assert not service.scan(ticket)
