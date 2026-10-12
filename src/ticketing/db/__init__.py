import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from ticketing.settings import get_settings


def make_engine() -> AsyncEngine:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return create_async_engine(
            get_settings().database_url, pool_pre_ping=True, poolclass=NullPool
        )
    return create_async_engine(
        get_settings().database_url, pool_pre_ping=True, pool_size=40, max_overflow=40
    )


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        async with session.begin():
            yield session
