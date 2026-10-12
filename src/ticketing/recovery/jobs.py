from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ticketing.inventory.postgres import release_expired
from ticketing.payments.webhook import reconcile_charges


async def run_recovery(session: AsyncSession, now: datetime) -> dict[str, int]:
    """Run bounded recovery jobs in one operator-triggered transaction."""
    released = await release_expired(session, now)
    reconciled = await reconcile_charges(session)
    return {"holds_released": released, "orders_reconciled": reconciled}
