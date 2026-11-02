from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import settings
from app.limiter.factory import create_limiter
from app.middleware import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.limiter = create_limiter(redis, settings)
    yield
    await redis.aclose()


app = FastAPI(title="RateGate", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/resource")
async def resource():
    return {"message": "You got through!"}
