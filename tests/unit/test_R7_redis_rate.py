import pytest

from ticketing.db.redis import make_redis
from ticketing.waitingroom.redis import allow


@pytest.mark.asyncio
async def test_R7_redis_token_bucket_sheds_after_burst() -> None:
    redis = make_redis()
    key = "test-rate"
    await redis.delete(f"rate:{key}")
    assert await allow(redis, key, rate=0.01, burst=1)
    assert not await allow(redis, key, rate=0.01, burst=1)
    await redis.aclose()
