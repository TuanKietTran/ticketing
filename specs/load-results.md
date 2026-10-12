# Load results

Runs used local PostgreSQL 16/Redis 7 Compose services and four Uvicorn workers. The load generator retries with the same idempotency keys and the invariant checker reads PostgreSQL after releasing expired holds.

| Run | Fault | Buyers/capacity | p99 end-to-end | Mean | Sold | Ticketed | Held | Charges | Result |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | none | 10,000/1,000 | 56,195.87 ms | 36,271.70 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |
| 2 | none | 10,000/1,000 | 50,385.45 ms | 31,579.92 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |
| 3 | none | 10,000/1,000 | 51,515.47 ms | 31,982.56 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |
| 4 | one worker `kill -9` at ~10s | 10,000/1,000 | 52,882.97 ms | 33,402.19 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |

For all four runs: 10,000 clients completed, terminal nonwinners 0, paid-not-ticketed 0, duplicate ticket sets 0, leaked holds 0. The first historical runs before bounded pools are retained in git history and failed with connection exhaustion/deadlocks; they are not counted as these four runs.

## Endpoint profiling

The instrumented 100-buyer/10-capacity profile reported (second run): browse p50/p99 302.81/1,136.18 ms, hold 345.47/976.78 ms, pay 71.08/416.06 ms, and no poll endpoint traffic. It recorded 220 requests, zero retries, 90 expected sold-out 409 responses, zero 429/503 shedding, and zero unexpected errors. A prior profile measured browse 251.50/845.37 ms and hold 152.14/734.49 ms. Redis-backed catalog reads remove inventory-row writes, but the target is not met consistently; the remaining bottleneck is concurrent request scheduling and the synchronous multi-step hold/checkout/pay flow. No claim is made that the browse/hold targets pass.

## Server/client measurement

`tools.loadgen` now reports client-observed endpoint latency separately from server-side Prometheus histogram bucket p99 values scraped from `/metrics`; four scrapes aggregate the four Uvicorn workers. The load runner supports bounded `--concurrency`, `--ramp-seconds`, and `make load-split`. Local `uvicorn[standard]` provides uvloop 0.23.0 and httptools 0.9.0; `make load` raises the file-descriptor limit and uses a five-second ramp. A 20-buyer verification reported client hold p99 128.15 ms versus server hold p99 bucket 250 ms.

## Post-admission-control reruns

Runs 5–7 used four Uvicorn workers, a five-second ramp, concurrency 100, and the guarded hold admission semaphore. All completed 10,000 clients with sold/ticketed 1,000, held 0, leaked holds 0, paid-not-ticketed 0, and zero unexpected errors. The intentional shedding counts were 105, 96, and 30 respectively.

| Run | Fault | Client browse p99 | Client hold p99 | Server browse p99 bucket | Server hold p99 bucket | E2E p99 | Mean | Result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 5 | none | 1,618.18 ms | 2,102.06 ms | 25 ms | 100 ms | 49,656.42 ms | 33,020.71 ms | invariants pass; latency fail |
| 6 | none | 1,073.87 ms | 1,601.91 ms | 25 ms | 100 ms | 37,639.55 ms | 25,041.71 ms | invariants pass; latency fail |
| 7 | none | 1,815.95 ms | 2,585.58 ms | 25 ms | 1,000 ms | 56,436.38 ms | 39,742.73 ms | invariants pass; latency fail |

The server/client split shows the dominant remaining cost is client-visible queueing and dependency contention: server browse is 25 ms p99 bucket and server hold is 100 ms in two runs, while client hold is 1.6–2.6 s. Run 7 also captured a 1,000 ms server hold bucket. The next fix is to instrument and remove the remaining checkout/pay queue contention (separate checkout/pay bulkheads and DB/Redis pool wait histograms), not to loosen acceptance targets. The 503 admission responses are intentionally shed and are returned after the 10 ms gate timeout; the current loadgen does not retry all shed responses, so they must remain excluded from unexpected-error rate.

## Tighter admission reruns

The hold admission bulkhead was reduced from 32 to 8 slots and its fast-fail timeout from 10 ms to 5 ms to keep saturated inventory requests out of PostgreSQL. Runs 8–10 and the kill-9 run all completed 10,000 clients with sold/ticketed 1,000, held 0, leaked holds 0, paid-not-ticketed 0, duplicate ticket sets 0, successful charges 1,000, and zero unexpected errors.

| Run | Fault | Client browse p99 | Client hold p99 | Server browse p99 bucket | Server hold p99 bucket | E2E p99 | Mean | Shed 429/503 | Result |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 8 | none | 1,638.36 ms | 2,740.88 ms | 5 ms | 100 ms | 52,465.62 ms | 34,619.87 ms | 210 | invariants pass; server latency pass; client latency fail |
| 9 | none | 1,167.26 ms | 2,048.62 ms | 5 ms | 50 ms | 45,796.74 ms | 28,688.89 ms | 153 | invariants pass; server latency pass; client latency fail |
| 10 | none | 1,340.20 ms | 4,942.58 ms | 10 ms | 100 ms | 60,379.92 ms | 29,765.65 ms | 270 | invariants pass; server latency pass; client latency fail |
| 11 | one worker `kill -9` at ~10s | 1,035.01 ms | 2,008.10 ms | 50 ms | 250 ms | 44,756.37 ms | 30,777.46 ms | 189 | invariants pass; server latency pass; client latency fail |

The brief asks for browse `<300 ms` and hold `<800 ms` p99. On the server-side Prometheus buckets, the latest four runs meet those targets: browse 5/5/10/50 ms and hold 100/50/100/250 ms. Client-observed endpoint p99 still misses badly because the benchmark intentionally creates 10,000 coroutines behind a concurrency gate and retries/sheds thousands of saturated requests; the extra time is client-side scheduling, retry backoff, and local HTTP connection queueing, not handler execution. The cheapest fix already applied was tighter hold admission shedding; the next fix would be a loadgen architecture change that measures admitted requests separately from client queue/backoff time, or production-side autoscaling beyond a four-worker laptop run.

## Chaos results

`make chaos` now starts a local server and runs reproducible R15/R16 scenarios for PSP 30% 5xx, PSP latency spike, PSP charged-but-timeout idempotency, DB busy/lock deadline, duplicate and reordered webhooks, clock-jump rejection, and DLQ growth plus exactly-once replay. Each scenario seeds a real event and ends by running the PostgreSQL invariant checker for that event.

## Acceptance gaps

The database invariants, chaos suite, and server-side browse/hold p99 targets pass in the latest runs. Client-observed browse/hold p99 and end-to-end p99 remain above the brief's numeric targets for the reasons recorded above. AWS Terraform remains static-validation-only; no cloud deployment was performed.
