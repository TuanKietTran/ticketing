# Final acceptance status

## Verified

- PostgreSQL/Redis persistence, guarded inventory, idempotency, payments, webhooks, tickets, refunds, outbox/DLQ, auth, waiting-room controls, Terraform, and named R1–R16 tests are implemented.
- `make test` passes (pytest and Ruff).
- Three post-optimization 10,000-buyer runs completed with exactly 1,000 sold/ticketed, zero oversell, zero leaked holds, zero paid-not-ticketed orders, and zero unexpected errors.
- Server Prometheus histograms are reported separately from client-observed latency. The three latest server browse p99 buckets were 25/25/25 ms; server hold buckets were 100/100/1,000 ms. Client browse p99 was 1,073.87–1,815.95 ms and client hold p99 was 1,601.91–2,585.58 ms.
- Intentional admission shedding returns 503 with `Retry-After`; the latest runs recorded 30–105 shed responses.
- `tools/chaos` exercises PSP failures, latency, charged-timeout idempotency, DB lock deadlines, webhook reorder, clock jumps, and DLQ growth/replay exactly once.

## Not passing / limits

The brief's client browse `<300 ms` and hold `<800 ms` targets are not met under the 10,000-client profile. The server-side handler is substantially faster than the client result; the remaining bottleneck is dependency/request queueing, especially checkout/pay and occasional DB/Redis contention. The next performance fix is pool-wait and per-stage instrumentation followed by separate checkout/pay bulkheads and pool sizing.

A kill-9 worker run was launched, but its final loadgen record was not available when this document was written; no success is claimed for that run. AWS Terraform was statically validated only; no AWS deployment was performed.
