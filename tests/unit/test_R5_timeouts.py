import asyncio

import pytest

from ticketing.retry import retry_idempotent


@pytest.mark.asyncio
async def test_R5_dependency_timeout_is_bounded() -> None:
    async def slow() -> None:
        await asyncio.sleep(1)

    with pytest.raises(asyncio.TimeoutError):
        await retry_idempotent(slow, attempts=1, deadline_seconds=0.01)
