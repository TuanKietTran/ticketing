# Load results

Runs used local PostgreSQL 16/Redis 7 Compose services and four Uvicorn workers. The load generator retries with the same idempotency keys and the invariant checker reads PostgreSQL after releasing expired holds.

| Run | Fault | Buyers/capacity | p99 end-to-end | Mean | Sold | Ticketed | Held | Charges | Result |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | none | 10,000/1,000 | 56,195.87 ms | 36,271.70 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |
| 2 | none | 10,000/1,000 | 50,385.45 ms | 31,579.92 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |
| 3 | none | 10,000/1,000 | 51,515.47 ms | 31,982.56 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |
| 4 | one worker `kill -9` at ~10s | 10,000/1,000 | 52,882.97 ms | 33,402.19 ms | 1,000 | 1,000 | 0 | 1,000 | invariant pass; latency fail |

For all four runs: 10,000 clients completed, terminal nonwinners 0, paid-not-ticketed 0, duplicate ticket sets 0, leaked holds 0. The first historical runs before bounded pools are retained in git history and failed with connection exhaustion/deadlocks; they are not counted as these four runs.

## Acceptance gaps

Browse and hold-specific p99 were not separately instrumented; the measured end-to-end p99 is far above the brief's `<300 ms browse` and `<800 ms hold` targets. Intentional 429/503 error rate was not separately reported. Full PSP 5xx/latency/charged-timeout, DB lock, webhook reorder, clock-jump, and DLQ-growth scenarios were not all exercised by the runner. The four invariant runs pass; the complete acceptance criteria do not.
