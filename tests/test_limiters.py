import asyncio

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.limiter.factory import create_limiter
from app.limiter.sliding_counter import SlidingWindowCounter
from app.limiter.sliding_log import SlidingWindowLog
from app.limiter.token_bucket import TokenBucket

# Every algorithm allows 5 requests, plus how long to wait until it allows again.
ALGORITHMS = {
    "token_bucket": (
        lambda redis: TokenBucket(redis, capacity=5, refill_rate=1.0),
        1.1,
    ),
    "sliding_log": (
        lambda redis: SlidingWindowLog(redis, limit=5, window_seconds=1),
        1.1,
    ),
    "sliding_counter": (
        lambda redis: SlidingWindowCounter(redis, limit=5, window_seconds=1),
        2.1,
    ),
}


def make(name, redis):
    build, _ = ALGORITHMS[name]
    return build(redis)


@pytest.mark.parametrize("name", ALGORITHMS)
async def test_allows_up_to_limit_then_blocks(redis, client_id, name):
    limiter = make(name, redis)
    results = [(await limiter.check(client_id)).allowed for _ in range(7)]
    assert results == [True] * 5 + [False] * 2


@pytest.mark.parametrize("name", ALGORITHMS)
async def test_blocked_decision_says_when_to_retry(redis, client_id, name):
    limiter = make(name, redis)
    for _ in range(5):
        await limiter.check(client_id)
    decision = await limiter.check(client_id)
    assert not decision.allowed
    assert decision.remaining == 0
    assert decision.retry_after > 0


@pytest.mark.parametrize("name", ALGORITHMS)
async def test_clients_have_separate_limits(redis, client_id, name):
    limiter = make(name, redis)
    for _ in range(5):
        await limiter.check(client_id)
    assert (await limiter.check(f"{client_id}-other")).allowed


@pytest.mark.parametrize("name", ALGORITHMS)
async def test_allows_again_after_waiting(redis, client_id, name):
    build, wait_seconds = ALGORITHMS[name]
    limiter = build(redis)
    for _ in range(5):
        await limiter.check(client_id)
    assert not (await limiter.check(client_id)).allowed
    await asyncio.sleep(wait_seconds)
    assert (await limiter.check(client_id)).allowed


@pytest.mark.parametrize(
    ("name", "expected_class"),
    [
        ("token_bucket", TokenBucket),
        ("sliding_log", SlidingWindowLog),
        ("sliding_counter", SlidingWindowCounter),
    ],
)
async def test_config_picks_the_algorithm(redis, name, expected_class):
    assert isinstance(create_limiter(redis, Settings(algorithm=name)), expected_class)


def test_unknown_algorithm_is_rejected():
    with pytest.raises(ValidationError):
        Settings(algorithm="leaky_bucket")
