# 000 Brief: ticketing system (3-hour build, Python + FastAPI)

Owner: the pi agent in this directory. Commander: the Claude session that wrote this. Do not ask back; decide, record the decision in `specs/DECISIONS.md` (one line each), keep moving.

## Goal
A production-grade event ticketing backend in Python/FastAPI that survives a flash sale: **10,000 concurrent purchase requests for 1,000 seats of one event with zero oversell, zero double charge, and every client retry safe.** Everything is verified by automated tests and a reproducible load/chaos run, not by claims.

## Stack (decided by the user: Python + FastAPI; Docker daemon is live)
- Python 3.13+ managed with `uv` (`pyproject.toml`, `uv.lock`; Python 3.14 is on the machine), FastAPI + uvicorn (multi-worker via gunicorn/uvicorn workers for the load run), Pydantic v2, SQLAlchemy 2 async + Alembic migrations, `asyncpg`.
- **PostgreSQL 16 (primary store) and Redis 7** run through `docker compose` (OrbStack is running; if `docker info` fails run `orbctl start`). Redis is used for rate limiting, the waiting-room queue, short idempotency claim locks and breaker/retry-budget counters; **Postgres stays the source of truth** for inventory, orders, idempotency records and the outbox (Redis loss must never cause oversell or double charge).
- Tests: `pytest`, `pytest-asyncio`, `hypothesis` (property tests for inventory), `httpx.AsyncClient`/`testcontainers` or the compose Postgres for integration tests. Lint/format `ruff`, types `mypy` (strict on core packages).
- Load generator and chaos runner in Python (`asyncio` + `httpx`, or `locust` if easier); no external binaries required.
- Never use `.mjs`. No AI attribution anywhere. No `CLAUDE.md`.

## Scope: cover ALL of these
1. **Catalog**: events, venues, sections, seats (reserved) and general admission (counted) inventory, price tiers, sale windows.
2. **Inventory and holds**: atomic seat/quantity holds with TTL; a hold is the only way to start checkout; reaper releases expired holds; conditional-update/row-lock design so oversell is impossible at the database level (CHECK constraints plus guarded UPDATE, not just app logic).
3. **Checkout and orders**: order state machine `pending -> awaiting_payment -> paid -> ticketed | failed | expired | cancelled | refunded` with transitions enforced in one place and every transition recorded in an append-only `order_events` table.
4. **Payments**: a PSP interface plus a mock PSP with configurable latency, timeouts, 5xx, duplicate webhooks, out-of-order webhooks, and "charged but response lost". Idempotent charge calls, webhook signature verification, reconciliation job that finds orders whose PSP state and ours disagree and repairs them.
5. **Ticket issuance**: signed tickets (HMAC/Ed25519 token in QR payload), exactly one ticket set per paid order (unique constraints), resend, transfer, void on refund.
6. **Check-in / scanning**: offline-verifiable signature, online one-time-use enforcement, safe under two simultaneous scans of the same ticket.
7. **Refunds and cancellations**: partial and full, idempotent, restocks inventory, compensating saga steps.
8. **Waiting room / admission control** for hot sales: bounded queue with tokens, fair ordering, expiry; protects the core under overload.
9. **Auth and tenancy**: API keys for organizers/admin, session tokens for buyers, per-organizer data isolation, constant-time secret comparison.
10. **Notifications and async work** via transactional **outbox** (order confirmation, ticket email stub, ticket issuance, refund steps) with a dispatcher that retries with exponential backoff + jitter and a max-attempt policy; exhausted messages move to a first-class **dead letter queue** (`dead_letters` table: payload, error history, attempts, first/last failure, origin, status). DLQ requirements: never lose a message, poison messages cannot block the queue, admin endpoints and CLI to list, inspect, replay (single and bulk, idempotent) and discard with reason, metrics and alerts on DLQ depth/age, replay safety proven by test (replaying twice has no extra effect). The same DLQ also receives unprocessable webhooks and failed recovery jobs.
11. **Admin**: sales dashboard endpoint, inventory view, force-release, DLQ replay, feature flags (pause sales).
12. **Observability**: structured logs (structlog or stdlib JSON) with request IDs, Prometheus-text `/metrics` (latency histograms, in-flight, queue depth, holds, oversell-guard rejections, retry counts, breaker state), `/healthz` (liveness) and `/readyz` (dependencies).
13. **Docs and ops**: README, API spec (`specs/api.md`, OpenAPI optional), runbook (`specs/runbook.md`: what to do on PSP outage, DB failover, stuck holds, DLQ growth), Dockerfile, compose (app + postgres + redis), Makefile (`make test load chaos`).

## "Defend hell": reliability requirements (the core of this project)
Every item needs a test that proves it. Name the test after the requirement id.
- R1 **Idempotency**: every mutating endpoint accepts `Idempotency-Key`; same key + same body returns the stored response (including original status code); same key + different body returns 422; concurrent duplicates execute once (key claimed atomically before work starts, in-flight duplicates wait or get 409 with `Retry-After`). Keys expire after 24h.
- R2 **No oversell, ever**: invariant `sold + held <= capacity` enforced by the database; property/fuzz test hammers it.
- R3 **Client retry storm**: a client that retries every request 3x with jitter (including after timeouts where the server did commit) causes no extra holds, orders or charges.
- R4 **Server-side retries** only on idempotent or idempotency-keyed operations: exponential backoff with full jitter, max attempts, overall deadline, retry budget (cap retries at ~10% of traffic) to avoid retry amplification. Never retry a non-idempotent call blindly.
- R5 **Timeouts everywhere**: server read/write/idle timeouts, per-request context deadlines, per-dependency timeouts, propagate cancellation; a cancelled request must not leave a half-applied state.
- R6 **Circuit breaker + bulkhead** around the PSP and around email: open on failure ratio, half-open probes; separate concurrency limits per dependency so a slow PSP cannot starve catalog reads.
- R7 **Load shedding and backpressure**: bounded worker pools and queues; when saturated return `429`/`503` with `Retry-After` quickly (fail fast, never queue unboundedly); priority: scans and payment webhooks over browse; rate limits per IP and per account (token bucket).
- R16 **Dead letters**: every async consumer has bounded retries then dead-letters; a test injects a poison message and a flapping dependency and asserts: queue keeps flowing, message lands in DLQ with full error history, replay after the fix succeeds exactly once, DLQ depth metric moves.
- R8 **Atomicity via saga + outbox**: no dual writes; DB change and its outbound event commit in one transaction; consumers are idempotent; compensation exists for every step (release hold, void charge, refund).
- R9 **Crash safety**: kill -9 at any point (after hold, after charge, before ticketing, mid-refund) then restart converges to a consistent state via recovery jobs (stuck order sweeper, hold reaper, reconciliation). Test with a fault-injection hook that panics at named points.
- R10 **Webhook hardening**: signature + timestamp tolerance, replay protection, dedupe by event id, out-of-order tolerance (state machine ignores stale events), always 2xx after durable record so PSP stops retrying.
- R11 **Graceful shutdown**: stop accepting, drain in-flight with deadline, flush outbox, release resources; readiness flips first.
- R12 **Input defense**: size limits, strict JSON decoding, validation, no SQL string building, safe pagination, request-ID and panic-recovery middleware that never leaks internals.
- R13 **Clock and ID safety**: injectable clock for tests; ULID/UUIDv7 ids; no reliance on wall-clock ordering for correctness.
- R14 **Data integrity**: money in integer minor units + currency, never floats; unique constraints for natural idempotency (one ticket per order-seat, one charge per order attempt); migrations versioned and forward-only.
- R15 **Chaos suite**: scripted scenarios against a running server: PSP 30% 5xx, PSP latency spike, PSP charged-but-timeout, DB busy/locked, duplicate and reordered webhooks, process kill and restart mid-sale, clock jump. Each ends by running the invariant checker.

## The 10k acceptance run (must be automated: `make load`)
Load generator (Python asyncio under `tools/loadgen`; the server runs with several uvicorn workers against the compose Postgres and Redis): 10,000 buyers hit one event with 1,000 seats, ramping in 5 seconds, each doing browse -> (waiting room if enabled) -> hold -> pay -> poll order, with 30% of clients retrying requests with the same idempotency key, 20% PSP failures injected, 5% duplicate webhooks.
Pass criteria, all checked by an invariant checker that reads the database after the run:
- exactly 1,000 orders ticketed (sold out), 0 oversell, 0 orders with more than one ticket set, 0 duplicate charges (mock PSP ledger vs orders match to the cent)
- every non-winning buyer got a clear terminal answer (sold out / failed / expired), none hung
- no leaked holds after TTL + reaper; outbox drained; DLQ empty or explained
- p99 latency of browse < 300 ms and hold < 800 ms on this laptop on the compose Postgres (state the numbers measured, do not guess); error rate other than intentional 429/503 shedding below 0.1%
- repeat the run 3 times, then once more with fault injection enabled and a mid-run `kill -9` of one worker; report all four results honestly in `specs/load-results.md` including failures and fixes.

## Working method
- Follow the repo convention: every todo into `specs/TODO.md` first, behaviour into numbered `specs/NNN-*.md` indexed in `specs/README.md`, tick off in the same change.
- Test-first for R1-R15. Parametrized tests; concurrency tests use real parallel requests against real Postgres, not mocks. Keep `ruff` and `mypy` clean.
- Small commits on `main`, pushed to the GitHub repo after each milestone (the commander creates the repo `TuanKietTran/ticketing` and sets `origin`; just `git push`). Author and committer: `mashallow <35926768+TuanKietTran@users.noreply.github.com>`, `-c commit.gpgsign=false`, no trailers of any kind.
- Layout: `src/ticketing/{api,catalog,inventory,orders,payments,tickets,checkin,refunds,waitingroom,auth,outbox,deadletter,admin,obs,db,clock,faults,settings}`, `alembic/`, `tests/{unit,integration,property,chaos}`, `tools/{loadgen,chaos,invariants}`, `specs/`, `deploy/`, `compose.yaml`, `Dockerfile`, `Makefile`.
- Do not spend more than ~15 minutes stuck on one problem: record it in TODO.md as a follow-up, choose the simplest correct alternative, continue.
- Never trust: re-run tests yourself before claiming something works; report failures plainly.

## Timeline (3 hours, wall clock from start)
- 0:00-0:20 specs (data model, state machine, API, invariants), repo skeleton, migrations, store interface, clock, faults, obs.
- 0:20-1:10 inventory/holds, orders, idempotency middleware, payments + mock PSP, webhooks, ticketing. Unit and race tests green.
- 1:10-1:50 outbox/dispatcher, refunds, check-in, auth, admin, waiting room, load shedding, breakers, graceful shutdown.
- 1:50-2:30 loadgen + invariant checker + chaos scenarios; first full 10k runs; fix what breaks.
- 2:30-2:50 harden from findings, Postgres store + compose (verify if Docker can start), runbook, README.
- 2:50-3:00 final: `make test load chaos` all green, results written to `specs/load-results.md`, TODO.md accurate, final summary file `specs/FINAL.md` (what exists, what was measured, what is unverified, known limits).
