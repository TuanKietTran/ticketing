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

## Acceptance gaps

Browse and hold-specific p99 were not separately instrumented; the measured end-to-end p99 is far above the brief's `<300 ms browse` and `<800 ms hold` targets. Intentional 429/503 error rate was not separately reported. Full PSP 5xx/latency/charged-timeout, DB lock, webhook reorder, clock-jump, and DLQ-growth scenarios were not all exercised by the runner. The four invariant runs pass; the complete acceptance criteria do not.
