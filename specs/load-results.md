# Load results

All runs used the local Compose PostgreSQL 16/Redis 7 services and four Uvicorn workers unless noted. Results are measurements, not acceptance claims.

## Historical run before bounded pool/retry fixes
- 10,000 buyers / 1,000 capacity completed in 44 seconds.
- p99 end-to-end flow: 40,588.29 ms; mean 26,174.74 ms.
- Only 328 ticketed and 672 active holds remained. PostgreSQL connection exhaustion and deadlocks were observed.

## Bounded-pool run
- 10,000 buyers / 1,000 capacity exceeded the host job SLA and was later observed complete.
- p99 end-to-end flow: 70,745.98 ms; mean 42,021.20 ms.
- Invariant snapshot at completion showed 328 sold and 672 held; therefore it failed the required 1,000 ticketed result.
- The load generator was then changed to cap client concurrency, retry the same idempotency keys, and always run the database checker.

## Verified smaller run after fixes
- 100 buyers / 10 capacity: 100 completed, 10 sold, 10 ticketed, 0 held, 0 leaked holds, 0 duplicate ticket sets, 10 successful charges; p99 60,395.00 ms.
- This proves the checker reads PostgreSQL and catches inventory/ticket state, but is not the required 10k acceptance.

## Passing 10k run after pool/gate fixes
- 10,000 buyers / 1,000 capacity completed in 58 seconds.
- p99 end-to-end flow: 56,195.87 ms; mean 36,271.70 ms.
- PostgreSQL invariant checker: held 0, sold 1,000, ticketed 1,000, terminal nonwinners 0, paid-not-ticketed 0, duplicate ticket sets 0, successful charges 1,000, leaked holds 0.
- The invariant criteria passed; the stated browse/hold latency targets were not separately instrumented and the end-to-end p99 is far above the brief target.

## Required repeats
Three passing normal 10k runs and one fault-injection/worker-kill run remain outstanding. Browse/hold-specific p99 and intentional-shedding error-rate measurements were not separately instrumented. No four-run acceptance claim is made.
