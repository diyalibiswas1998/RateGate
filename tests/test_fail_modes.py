import time

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.limiter.token_bucket import TokenBucket
from app.main import app
from app.redis_client import create_redis

# Nothing listens on this port, so every Redis command fails like during an outage.
DOWN_URL = "redis://127.0.0.1:6399/0"


@pytest.fixture
async def redis_down():
    client = create_redis(Settings(redis_url=DOWN_URL))
    yield client
    await client.aclose()


async def call_api(limiter, fail_mode, api_key, times=1):
    """Send requests through the real app and middleware, using the given limiter."""
    app.state.limiter = limiter
    app.state.fail_mode = fail_mode
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-API-Key": api_key}
        return [
            await client.get("/api/resource", headers=headers) for _ in range(times)
        ]


async def test_fail_open_allows_requests_when_redis_is_down(redis_down, client_id):
    [response] = await call_api(TokenBucket(redis_down, 10, 1.0), "open", client_id)
    assert response.status_code == 200
    assert "x-ratelimit-limit" not in response.headers


async def test_fail_closed_rejects_requests_when_redis_is_down(redis_down, client_id):
    [response] = await call_api(TokenBucket(redis_down, 10, 1.0), "closed", client_id)
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"


async def test_outage_is_detected_within_the_timeouts(redis_down, client_id):
    # Worst case: the attempt and its one retry each wait the full connect timeout.
    budget = 2 * settings.redis_connect_timeout + 0.5
    start = time.perf_counter()
    await call_api(TokenBucket(redis_down, 10, 1.0), "open", client_id)
    assert time.perf_counter() - start < budget


async def test_limiting_resumes_after_an_outage(redis, redis_down, client_id):
    healthy = TokenBucket(redis, capacity=2, refill_rate=0.001)
    broken = TokenBucket(redis_down, capacity=2, refill_rate=0.001)
    before = await call_api(healthy, "closed", client_id)
    during = await call_api(broken, "closed", client_id, times=2)
    after = await call_api(healthy, "closed", client_id, times=2)
    codes = [response.status_code for response in before + during + after]
    assert codes == [200, 503, 503, 200, 429]


def test_fail_mode_accepts_only_open_or_closed():
    assert Settings(fail_mode="closed").fail_mode == "closed"
    with pytest.raises(ValidationError):
        Settings(fail_mode="maybe")
