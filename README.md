# RateGate

[![CI](https://github.com/diyalibiswas1998/RateGate/actions/workflows/ci.yml/badge.svg)](https://github.com/diyalibiswas1998/RateGate/actions/workflows/ci.yml)

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

On Windows with Docker Desktop, Redis replies can be delayed under bursts, beyond the production timeouts. Give this machine its own values in a `.env` file (never committed; the containers don't read it):

```
RATEGATE_REDIS_SOCKET_TIMEOUT=1.0
RATEGATE_REDIS_CONNECT_TIMEOUT=1.5
```

## Run the full stack (3 copies behind nginx)

```bash
docker compose up --build -d --wait
```

This starts Redis, three copies of the API and nginx, which spreads requests across the copies in turn. Call `http://127.0.0.1:8080/api/resource`: the `X-Instance-Id` header names the copy that answered, while every copy checks the same Redis, so a client is limited once, globally.

```bash
uv run python scripts/sequential_requests.py                 # one at a time: copies take turns
uv run python scripts/concurrent_burst.py --url http://127.0.0.1:8080/api/resource
docker compose down                                         # stop and remove everything
```

Settings from your terminal (for example `RATEGATE_ALGORITHM` or `RATEGATE_CAPACITY`) are passed into the copies. Behind nginx, clients without an API key are identified by their real IP, taken from the `X-Forwarded-For` header that nginx sets.

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

Short timeouts (1 s to connect, 0.25 s per command) keep outages from freezing requests: a hung Redis is detected in about 0.25 s and a stopped one in about 1 s. A command whose connection turns out to be dead (for example after a Redis restart) is retried once, immediately; a timed-out command is not, because the script may already have run and would count the request twice. Limiting resumes by itself as soon as Redis returns, with no restart.

## Testing

`uv run pytest` runs 40 tests against a real Redis, including:

- **Concurrency:** 200 simultaneous requests against a limit of 100 allow exactly 100, for every algorithm, from one client and from four independent clients. A deliberately non-atomic limiter in the same test lets all 200 through, showing the test can detect a race.
- **Boundaries:** waiting the returned `Retry-After` is always enough; idle keys expire on schedule; no double burst across a window boundary.
- **Failure handling:** with Redis unreachable, fail-open returns `200` and fail-closed returns `503`, within the configured timeouts; limiting resumes where it left off once Redis is back.
- **No double counting:** a request whose reply times out is counted once, never retried into a second count.
- **Instance id:** every response, including `429`, carries `X-Instance-Id`.

Every push runs the same checks on GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): lint, formatting and all tests against a Redis service container, plus a job that starts the full Docker stack and checks that a burst of 200 requests through nginx is allowed exactly the limit (100) across 3 copies.

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
| `RATEGATE_INSTANCE_ID` | the hostname | All: the `X-Instance-Id` value; in a container, its ID |
| `RATEGATE_ALGORITHM` | `token_bucket` | All |
| `RATEGATE_CAPACITY` | `10` | Token bucket: burst size |
| `RATEGATE_REFILL_RATE` | `1.0` | Token bucket: tokens per second |
| `RATEGATE_LIMIT` | `10` | Sliding windows: requests per window |
| `RATEGATE_WINDOW_SECONDS` | `10.0` | Sliding windows: window length |
