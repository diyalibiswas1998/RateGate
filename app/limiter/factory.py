from redis.asyncio import Redis

from app.config import Settings
from app.limiter.base import RateLimitStrategy
from app.limiter.sliding_counter import SlidingWindowCounter
from app.limiter.sliding_log import SlidingWindowLog
from app.limiter.token_bucket import TokenBucket


def create_limiter(redis: Redis, settings: Settings) -> RateLimitStrategy:
    if settings.algorithm == "token_bucket":
        return TokenBucket(redis, settings.capacity, settings.refill_rate)
    if settings.algorithm == "sliding_log":
        return SlidingWindowLog(redis, settings.limit, settings.window_seconds)
    if settings.algorithm == "sliding_counter":
        return SlidingWindowCounter(redis, settings.limit, settings.window_seconds)
    raise ValueError(f"Unknown algorithm: {settings.algorithm}")
