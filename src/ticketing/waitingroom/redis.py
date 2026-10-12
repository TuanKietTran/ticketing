import time

from redis.asyncio import Redis

_BUCKET = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local burst = tonumber(ARGV[3])
local state = redis.call('HMGET', key, 'tokens', 'at')
local tokens = tonumber(state[1]) or burst
local at = tonumber(state[2]) or now
 tokens = math.min(burst, tokens + (now - at) * rate)
if tokens < 1 then return 0 end
redis.call('HMSET', key, 'tokens', tokens - 1, 'at', now)
redis.call('EXPIRE', key, math.ceil(burst / rate) + 1)
return 1
"""


async def allow(redis: Redis, identity: str, rate: float, burst: int) -> bool:
    result = await redis.eval(_BUCKET, 1, f"rate:{identity}", time.time(), rate, burst)
    return bool(result)
