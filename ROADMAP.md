# RateGate Roadmap

Each phase has one **intent** (why it exists), the **tasks**, a **done when** check you can verify yourself,
and **what you learn**. Finish a phase, verify it, commit, then move on. Never start a phase with the previous one broken.

**Working loop for every phase:** understand → build the smallest thing → test it → run it → commit → note what you learned.

---

## Phase 0 — Setup
**Intent:** a reproducible environment, so "works on my machine" never happens.

- [x] Install `uv` (`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`)
- [x] `git init` + `.gitignore` (done by `uv init`)
- [ ] Create a public GitHub repo and push (you do this, see below)
- [x] `uv init`, pin Python 3.12 (`uv python pin 3.12`)
- [x] Add deps: `fastapi uvicorn[standard] redis pydantic-settings`; dev: `pytest httpx ruff`
- [x] Run Redis in Docker: `docker run -d -p 6379:6379 --name redis redis:7`

**Done when:** `docker exec redis redis-cli ping` returns `PONG` and `uv run python -c "import fastapi, redis"` works.
**You learn:** dependency management, lockfiles, containers.

---

## Phase 1 — One API, one algorithm (token bucket)
**Intent:** prove the core idea end to end before adding abstractions.

- [ ] FastAPI app with a `/api/resource` demo route and `/health`
- [ ] Token bucket as a **Lua script** (read tokens, refill by elapsed time, take one, write back — all atomic)
- [ ] Use `redis.call('TIME')` inside Lua, never the app server's clock
- [ ] Middleware: identify the client (API key header, fallback to IP), call the limiter
- [ ] Blocked → `429` + `Retry-After`; always send `X-RateLimit-Limit / Remaining / Reset`

**Done when:** hitting the endpoint in a loop gives 200s then 429s, and tokens refill after waiting.
**You learn:** token bucket math, Lua atomicity, FastAPI middleware, HTTP semantics.

---

## Phase 2 — Strategy interface + two more algorithms
**Intent:** make algorithms swappable so you can compare their trade-offs.

- [ ] `RateLimitStrategy` abstract class returning a `Decision(allowed, remaining, reset_after, retry_after)`
- [ ] Refactor token bucket into it
- [ ] Sliding window log (Redis sorted set: `ZREMRANGEBYSCORE` + `ZCARD` + `ZADD`)
- [ ] Sliding window counter (current + previous window, weighted)
- [ ] Choose algorithm + limits via config / env vars
- [ ] Write in the README: memory cost vs accuracy vs burst behaviour of each

**Done when:** switching `RATEGATE_ALGORITHM` changes behaviour with no code edits; each algorithm has unit tests.
**You learn:** strategy pattern, Redis data structures, algorithm trade-offs.

---

## Phase 3 — Correctness under concurrency
**Intent:** prove the "no race conditions" claim with evidence, not words.

- [ ] Tests run against **real Redis** (not fakeredis — its Lua support is partial)
- [ ] Concurrency test: limit 100, fire 200 simultaneous requests → exactly 100 allowed
- [ ] Boundary tests: refill timing, window edges, key expiry (`PEXPIRE` so idle clients don't leak memory)

**Done when:** `uv run pytest` is green, and the concurrency test passes repeatedly.
**You learn:** race conditions, why atomic scripts matter, writing meaningful tests.

---

## Phase 4 — Failure handling (fail-open / fail-closed)
**Intent:** decide what happens when Redis is down, instead of letting the app crash.

- [ ] Short Redis socket/connect timeouts (e.g. 50–100 ms)
- [ ] `RATEGATE_FAIL_MODE=open` → allow + log warning; `closed` → `503`
- [ ] Test: stop Redis mid-test and assert each mode's behaviour

**Done when:** `docker stop redis` → API still responds according to the configured mode.
**You learn:** resilience design, availability vs protection trade-off.

---

## Phase 5 — Horizontal scaling
**Intent:** demonstrate the headline claim — limits hold across multiple instances.

- [ ] `Dockerfile` for the API
- [ ] `docker-compose.yml`: Redis + 3 API replicas + nginx (round-robin)
- [ ] Each response includes an `X-Instance-Id` header
- [ ] Test/script: requests spread across all 3 instances still stop at exactly the limit

**Done when:** `docker compose up` → responses come from different instances, but the client is limited once, globally.
**You learn:** shared state, load balancing, container orchestration basics.

---

## Phase 6 — CI with GitHub Actions
**Intent:** every push is automatically checked.

- [ ] Workflow: install `uv` → `ruff check` → `ruff format --check` → `pytest`
- [ ] Redis as a **service container** in the workflow
- [ ] CI badge in README

**Done when:** a pushed commit shows a green check on GitHub; a deliberately broken test turns it red.
**You learn:** CI pipelines, service containers.

---

## Phase 7 — Load testing with Locust
**Intent:** measure, don't guess.

- [ ] `loadtest/locustfile.py` with several simulated clients
- [ ] Run against the 3-replica compose setup
- [ ] Record RPS, p50/p95 latency, % 429s per algorithm → table in README

**Done when:** README contains real numbers from your machine.
**You learn:** load testing, latency percentiles, reading results honestly.

---

## Phase 8 — Polish (optional)
- [ ] `/metrics` with `prometheus-client` (allowed / blocked / fail-open counters)
- [ ] Architecture diagram + "design decisions" section in README
- [ ] Per-route or per-tier limits (e.g. free vs paid API keys)

---

## Progress log
| Date | Phase | What I learned / problems hit |
|------|-------|-------------------------------|
|      |       |                               |
