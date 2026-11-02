# RateGate

A distributed rate-limiting service built with FastAPI and Redis. Every API instance checks limits against the same Redis, using atomic Lua scripts, so a client's limit holds no matter which instance answers.

Over the limit, clients get `429 Too Many Requests` with a `Retry-After` header. Every response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`.

## Run it

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```bash
docker run -d -p 6379:6379 --name redis redis:7
uv sync
uv run uvicorn app.main:app --reload
```

Then call `http://127.0.0.1:8000/api/resource`. Clients are identified by the `X-API-Key` header, or by IP address if it's missing.

Run the tests (Redis must be running):

```bash
uv run pytest
```

## Algorithms

Choose with `RATEGATE_ALGORITHM` (`token_bucket` | `sliding_log` | `sliding_counter`). All three sit behind one `RateLimitStrategy` interface, so the middleware doesn't know which one is running.

| | Token bucket | Sliding window log | Sliding window counter |
|---|---|---|---|
| Memory per client | 2 numbers | 1 entry per request in the window | 3 numbers |
| Accuracy | Exact | Exact | Approximate |
| After a burst | Refills gradually | Nothing until a full window passes | Fades gradually from the next window |
| Redis type | Hash | Sorted set | Hash |

## Configuration

| Variable | Default | Used by |
|---|---|---|
| `RATEGATE_REDIS_URL` | `redis://localhost:6379/0` | All |
| `RATEGATE_ALGORITHM` | `token_bucket` | All |
| `RATEGATE_CAPACITY` | `10` | Token bucket: burst size |
| `RATEGATE_REFILL_RATE` | `1.0` | Token bucket: tokens per second |
| `RATEGATE_LIMIT` | `10` | Sliding windows: requests per window |
| `RATEGATE_WINDOW_SECONDS` | `10.0` | Sliding windows: window length |
