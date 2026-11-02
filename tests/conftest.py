from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.config import settings


@pytest.fixture
async def redis():
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def client_id():
    # A fresh id per test, so tests never share a bucket or wait for old keys to expire.
    return f"test-{uuid4()}"
