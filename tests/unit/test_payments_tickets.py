import asyncio
from uuid import uuid4

from ticketing.payments.mock import MockPSP
from ticketing.tickets.service import TicketService


def test_psp_charge_and_webhook_signature() -> None:
    async def run():
        psp = MockPSP()
        order = uuid4()
        charge = await psp.charge(order, 1250)
        assert await psp.charge(order, 1250) == charge
        signature, raw = psp.signed_webhook("evt", {"charge": charge.id}, "100")
        assert psp.verify(raw, signature, "100", 100)

    asyncio.run(run())


def test_ticket_issue_and_scan_are_once_only() -> None:
    service = TicketService("secret")
    tickets = service.issue_once(uuid4(), 1)
    assert service.issue_once(tickets[0].order_id, 1) == tickets
    assert service.scan(tickets[0])
    assert not service.scan(tickets[0])
