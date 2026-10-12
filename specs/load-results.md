# Load results

## Run 1
- Command: `make load` equivalent with four Uvicorn workers, 10,000 buyers, capacity 1,000.
- Result: completed 10,000 requests; measured p99 end-to-end buyer flow **40,588.29 ms**, mean **26,174.74 ms**.
- This does **not** meet the brief's browse/hold latency targets. Browse and hold-only percentiles were not instrumented.
- The current load runner does not yet read PostgreSQL invariants, so ticket/order/charge/DLQ acceptance criteria are unverified.

## Required repeats
Runs 2, 3, and the fault-injection run were not completed in this build. No claim of four-run acceptance is made.

## Chaos
The baseline chaos command passed against four Uvicorn workers and `/healthz`. The required PSP, database-lock, webhook-reordering, process-kill, and clock-jump scenarios remain unverified.
