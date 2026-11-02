from dataclasses import dataclass
from pathlib import Path

from redis.asyncio import Redis

LUA_SCRIPT = (Path(__file__).parent / "scripts" / "token_bucket.lua").read_text(encoding="utf-8")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: float  # seconds until the next request would be allowed (0 if allowed)
    reset_after: float  # seconds until the bucket is completely full again


class TokenBucket:
    def __init__(self, redis: Redis, capacity: int, refill_rate: float) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._script = redis.register_script(LUA_SCRIPT)

    async def check(self, client_id: str, cost: int = 1) -> Decision:
        key = f"rategate:tb:{client_id}"
        allowed, remaining, retry_ms, reset_ms = await self._script(
            keys=[key], args=[self.capacity, self.refill_rate, cost]
        )
        return Decision(
            allowed=bool(allowed),
            limit=self.capacity,
            remaining=int(remaining),
            retry_after=retry_ms / 1000,
            reset_after=reset_ms / 1000,
        )
