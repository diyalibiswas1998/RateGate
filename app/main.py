from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.limiter.factory import create_limiter
from app.middleware import RateLimitMiddleware
from app.redis_client import create_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = create_redis(settings)
    app.state.limiter = create_limiter(redis, settings)
    app.state.fail_mode = settings.fail_mode
    yield
    await redis.aclose()


app = FastAPI(title="RateGate", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def add_instance_id(request, call_next):
    # Added last, so it wraps everything: 200s, 429s and 503s all say who answered.
    response = await call_next(request)
    response.headers["X-Instance-Id"] = settings.instance_id
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/resource")
async def resource():
    return {"message": "You got through!"}
