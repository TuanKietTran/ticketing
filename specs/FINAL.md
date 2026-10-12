# Final acceptance status

## Verified

- PostgreSQL/Redis persistence, guarded inventory, idempotency, payments, webhooks, tickets, refunds, outbox/DLQ, auth, waiting-room controls, Terraform, and named R1–R16 tests are implemented.
- `make test` passes (pytest and Ruff).
- `make chaos` is reproducible: it starts a local server and exercises PSP 30% 5xx, PSP latency spike, PSP charged-but-timeout idempotency, DB busy/lock, duplicate and reordered webhooks, clock-jump rejection, and DLQ growth plus exactly-once replay. Every scenario seeds a real event and ends with the PostgreSQL invariant checker.
- Three latest normal 10,000-buyer runs and one kill-9 worker run completed with exactly 1,000 sold/ticketed, zero oversell, zero leaked holds, zero paid-not-ticketed orders, zero duplicate ticket sets, 1,000 successful charges, and zero unexpected errors.
- Server Prometheus histograms are reported separately from client-observed latency. The latest four server browse p99 buckets were 5/5/10/50 ms and server hold p99 buckets were 100/50/100/250 ms, meeting the brief's server-side browse `<300 ms` and hold `<800 ms` targets.
- Intentional admission shedding returns 503 with `Retry-After`; the latest runs recorded 153–270 shed responses.

## Not passing / limits

Client-observed browse and hold p99 still miss the numeric targets under the 10,000-client profile: browse p99 was 1,035.01–1,638.36 ms and hold p99 was 2,008.10–4,942.58 ms. The server-side metrics show handler time is within target; the remaining bottleneck is client-side scheduling, retry backoff, and local HTTP connection queueing from 10,000 coroutines behind a 100-concurrency gate plus intentional shedding. The cheapest server fix was applied by tightening hold admission from 32 to 8 slots and 10 ms to 5 ms fast-fail. The next fix would be to report admitted-request latency separately in the load generator or scale beyond four local workers.

AWS Terraform was statically validated only; no AWS deployment was performed.
