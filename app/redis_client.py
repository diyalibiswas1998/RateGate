from redis.asyncio import BlockingConnectionPool, Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff

from app.config import Settings


def create_redis(settings: Settings) -> Redis:
    # A blocking pool makes a burst of requests wait briefly for a free connection
    # instead of failing with "Too many connections".
    pool = BlockingConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        timeout=settings.redis_pool_timeout,
        socket_connect_timeout=settings.redis_connect_timeout,
        socket_timeout=settings.redis_socket_timeout,
        # One immediate retry replaces a connection that went stale (e.g. Redis
        # restarted); more retries would only delay noticing a real outage.
        retry=Retry(NoBackoff(), retries=1),
        decode_responses=True,
    )
    return Redis.from_pool(pool)
