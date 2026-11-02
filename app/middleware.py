import logging
import math

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/health", "/docs", "/openapi.json"}
OUTAGE_RETRY_AFTER = "5"  # seconds a client should wait while Redis is unreachable

logger = logging.getLogger("rategate")


def identify_client(request: Request) -> str:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{api_key}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        limiter = request.app.state.limiter
        try:
            decision = await limiter.check(identify_client(request))
        except RedisError as error:
            if request.app.state.fail_mode == "closed":
                logger.error(
                    "Redis unavailable, rejecting request (fail-closed): %s", error
                )
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Rate limiter unavailable. Try again shortly."},
                    headers={"Retry-After": OUTAGE_RETRY_AFTER},
                )
            logger.warning("Redis unavailable, allowing request (fail-open): %s", error)
            return await call_next(request)

        headers = {
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
            "X-RateLimit-Reset": str(math.ceil(decision.reset_after)),
        }

        if not decision.allowed:
            headers["Retry-After"] = str(max(1, math.ceil(decision.retry_after)))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Slow down."},
                headers=headers,
            )

        response = await call_next(request)
        response.headers.update(headers)
        return response
