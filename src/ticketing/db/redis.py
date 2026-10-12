from redis.asyncio import Redis

from ticketing.settings import get_settings


def make_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)
