from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ticketing.inventory.postgres import claim_general_admission
from ticketing.orders.postgres import checkout_hold
from ticketing.payments.mock import MockPSP
from ticketing.payments.postgres import record_charge
from ticketing.payments.webhook import receive_webhook
from ticketing.refunds.postgres import refund_order
from ticketing.tickets.postgres import issue_ticket_set, scan_ticket


@pytest.mark.asyncio
async def test_R8_persistent_checkout_charge_ticket_and_atomic_scan() -> None:
    engine = create_async_engine("postgresql+asyncpg://ticketing:ticketing@localhost:5432/ticketing")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    organizer, event, section, buyer = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE organizers CASCADE"))
        await connection.execute(text("TRUNCATE webhook_events"))
        await connection.execute(
            text("INSERT INTO organizers(id,name,api_key_hash) VALUES (:id,'flow','hash')"),
            {"id": organizer},
        )
        await connection.execute(
            text(
                "INSERT INTO events(id,organizer_id,name,sale_opens_at,sale_closes_at) "
                "VALUES (:id,:org,'flow',:open,:close)"
            ),
            {
                "id": event,
                "org": organizer,
                "open": now - timedelta(hours=1),
                "close": now + timedelta(hours=1),
            },
        )
        await connection.execute(
            text(
                "INSERT INTO sections(id,event_id,name,mode,capacity) "
                "VALUES (:id,:event,'GA','general_admission',1)"
            ),
            {"id": section, "event": event},
        )
    async with factory() as session:
        async with session.begin():
            hold_id = await claim_general_admission(
                session, event, section, buyer, "flow-1", 1, now + timedelta(minutes=10)
            )
            assert hold_id is not None
    async with factory() as session:
        async with session.begin():
            order_id = await checkout_hold(session, hold_id, now)
            await record_charge(session, order_id, 1000, "USD", "provider-1")
            psp = MockPSP()
            signature, raw = psp.signed_webhook(
                "event-1", {"order_id": str(order_id), "status": "succeeded"}, "100"
            )
            processed = await receive_webhook(
                session, psp, "event-1", raw, signature, "100", 100
            )
            duplicate = await receive_webhook(
                session, psp, "event-1", raw, signature, "100", 100
            )
            assert processed == "processed"
            assert duplicate == "duplicate"
    async with factory() as session:
        async with session.begin():
            tickets = await issue_ticket_set(session, order_id, 1, "test-signing-key")
    assert len(tickets) == 1
    async with factory() as session:
        async with session.begin():
            first_scan = await scan_ticket(session, tickets[0], "device-a")
    async with factory() as session:
        async with session.begin():
            second_scan = await scan_ticket(session, tickets[0], "device-b")
            refund_id = await refund_order(session, order_id, 1000, 1)
            state = (
                await session.execute(
                    text("SELECT state FROM orders WHERE id=:id"), {"id": order_id}
                )
            ).scalar_one()
            ticket_state = (
                await session.execute(
                    text("SELECT state FROM tickets WHERE id=:id"), {"id": tickets[0]}
                )
            ).scalar_one()
            event_count = (
                await session.execute(
                    text("SELECT count(*) FROM order_events WHERE order_id=:id"), {"id": order_id}
                )
            ).scalar_one()
    assert first_scan and not second_scan
    assert refund_id
    assert state == "refunded"
    assert ticket_state == "void"
    assert event_count == 3
    await engine.dispose()
