import base64
import hashlib
import hmac
import json
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def issue_ticket_set(
    session: AsyncSession, order_id: UUID, quantity: int, signing_key: str
) -> list[UUID]:
    """Create one set per order; retries return the existing set's tickets."""
    ticket_set = (
        await session.execute(
            text(
                "INSERT INTO ticket_sets(order_id) VALUES (:order) "
                "ON CONFLICT (order_id) DO NOTHING RETURNING id"
            ),
            {"order": order_id},
        )
    ).scalar_one_or_none()
    if ticket_set is None:
        rows = await session.execute(
            text("SELECT id FROM tickets WHERE order_id=:order"), {"order": order_id}
        )
        return [UUID(str(row[0])) for row in rows]
    ticket_ids: list[UUID] = []
    for _ in range(quantity):
        ticket_id = uuid4()
        payload = base64.urlsafe_b64encode(
            json.dumps(
                {"ticket_id": str(ticket_id), "order_id": str(order_id)}, sort_keys=True
            ).encode()
        ).decode()
        signature = hmac.new(signing_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        await session.execute(
            text(
                "INSERT INTO tickets(id,order_id,token_hash,token_payload,state) "
                "VALUES (:id,:order,:hash,:payload,'valid')"
            ),
            {
                "id": ticket_id,
                "order": order_id,
                "hash": hashlib.sha256(f"{payload}.{signature}".encode()).hexdigest(),
                "payload": f"{payload}.{signature}",
            },
        )
        ticket_ids.append(ticket_id)
    return ticket_ids


async def scan_ticket(session: AsyncSession, ticket_id: UUID, device_id: str) -> bool:
    result = await session.execute(
        text(
            "INSERT INTO scans(ticket_id,device_id) VALUES (:ticket,:device) "
            "ON CONFLICT (ticket_id) DO NOTHING"
        ),
        {"ticket": ticket_id, "device": device_id},
    )
    return result.rowcount == 1
