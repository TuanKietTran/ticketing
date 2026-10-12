import hashlib
import hmac
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def authenticate_organizer(session: AsyncSession, api_key: str) -> UUID | None:
    digest = hash_api_key(api_key)
    row = (
        await session.execute(
            text("SELECT id FROM organizers WHERE api_key_hash=:hash"), {"hash": digest}
        )
    ).scalar_one_or_none()
    return UUID(str(row)) if row is not None else None


def constant_time_equal(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode(), expected.encode())
