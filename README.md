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

## Failure handling

If Redis can't be reached, `RATEGATE_FAIL_MODE` decides:

- `open` (default): requests are allowed without limiting, and a warning is logged.
- `closed`: requests get `503 Service Unavailable` with `Retry-After: 5`, and an error is logged.

Short timeouts (1 s to connect, 0.25 s per command) and a single immediate retry keep outages from freezing requests: a hung Redis is detected in about 0.5 s. Limiting resumes by itself as soon as Redis returns, with no restart.

## Testing

`uv run pytest` runs 36 tests against a real Redis, including:

- **Concurrency:** 200 simultaneous requests against a limit of 100 allow exactly 100, for every algorithm, from one client and from four independent clients. A deliberately non-atomic limiter in the same test lets all 200 through, showing the test can detect a race.
- **Boundaries:** waiting the returned `Retry-After` is always enough; idle keys expire on schedule; no double burst across a window boundary.
- **Failure handling:** with Redis unreachable, fail-open returns `200` and fail-closed returns `503`, within the configured timeouts; limiting resumes where it left off once Redis is back.

End to end against a running server:

```bash
uv run python scripts/concurrent_burst.py --total 200
```

## Configuration

| Variable | Default | Used by |
|---|---|---|
| `RATEGATE_REDIS_URL` | `redis://localhost:6379/0` | All |
| `RATEGATE_REDIS_MAX_CONNECTIONS` | `50` | All: Redis connections shared by all requests |
| `RATEGATE_REDIS_POOL_TIMEOUT` | `5.0` | All: seconds a request waits for a free connection |
| `RATEGATE_REDIS_CONNECT_TIMEOUT` | `1.0` | All: seconds to open a Redis connection |
| `RATEGATE_REDIS_SOCKET_TIMEOUT` | `0.25` | All: seconds to wait for a Redis reply |
| `RATEGATE_FAIL_MODE` | `open` | All: `open` or `closed` when Redis is unreachable |
| `RATEGATE_ALGORITHM` | `token_bucket` | All |
| `RATEGATE_CAPACITY` | `10` | Token bucket: burst size |
| `RATEGATE_REFILL_RATE` | `1.0` | Token bucket: tokens per second |
| `RATEGATE_LIMIT` | `10` | Sliding windows: requests per window |
| `RATEGATE_WINDOW_SECONDS` | `10.0` | Sliding windows: window length |
