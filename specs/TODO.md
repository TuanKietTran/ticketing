# TODO

## Gap analysis (against specs/000-brief.md)
- [x] Replace in-memory reference services with real async SQLAlchemy/PostgreSQL persistence and Redis integration.
- [x] Add complete forward-only Alembic migrations for organizers, catalog, inventory, holds, orders, order_events, idempotency, charges, tickets, scans, webhooks, outbox, and dead_letters, including CHECK/unique constraints.
- [x] Implement guarded SQL inventory UPDATEs, hold TTL/reaper, reserved seats, general admission, and real 200-way PostgreSQL race tests on 10 seats.
- [x] Implement HTTP Idempotency-Key middleware with atomic claim, body mismatch 422, replayed status/body, expiry, concurrent duplicate waiting/409, and R1/R3 tests.
- [x] Implement complete order/payment persistence, PSP retry/timeout/failure modes, signed durable webhook endpoint, dedupe/out-of-order handling, reconciliation, and charge ledger.
- [x] Implement transactional outbox dispatcher with exponential full-jitter backoff, bounded retries, poison-message DLQ, DLQ metrics/alerts, admin list/inspect/replay bulk/discard endpoints, CLI, and R16 replay tests.
- [x] Implement refunds/cancellations with compensating saga, partial/full idempotency, restock, ticket voiding, and recovery jobs.
- [x] Implement ticket transfer/resend, signed offline verification, and atomic online check-in race tests.
- [x] Implement API-key/session auth, tenant isolation, constant-time comparison, and authenticated admin operations.
- [x] Implement waiting-room tokens/fair expiry, Redis token bucket rate limits, bounded queues, load shedding, priority handling, PSP/email circuit breakers, bulkheads, retry budgets, and dependency deadlines.
- [x] Implement structured metrics (latency/in-flight/holds/oversell/retries/breaker/DLQ), readiness dependency checks, request limits, strict validation, panic recovery, and graceful shutdown/draining.
- [x] Implement crash recovery fault hooks, stuck-order/hold/reconciliation workers, and R9/R10/R11/R12/R13/R14 tests.
- [x] Implement Docker Compose migrations/worker topology and verify real PostgreSQL 16 + Redis 7 startup.
- [x] Add named test_R1_* through test_R16_* coverage, property/fuzz tests, integration tests against compose services, and clean mypy/ruff.
- [x] Make loadgen ramp 10k buyers, retries/failures/duplicate webhooks; make invariant checker read PostgreSQL and assert exactly 1000 ticketed, no oversell, ledger equality, no leaked holds, drained outbox/DLQ.
- [ ] Run three normal 10k acceptance runs plus one kill/fault run; record measured browse/hold p99, error rate, and every failure honestly.
- [ ] Update README/runbook/specs/FINAL.md with verified scope and known limits; commit/push each milestone with required identity/signing/trailer rules.
- [x] Add AWS Terraform under infra/terraform: bootstrap remote state, staging/prod VPC/ALB+ACM/ECS api-worker-dispatcher/ECR/RDS16 Multi-AZ prod/ElastiCache/Secrets/IAM/alarms/autoscaling/WAF/OIDC.
- [x] Add multi-stage non-root Dockerfile healthcheck, ECS one-off migration task, infra README first deploy/rollback/destroy/cost ESTIMATE/unverified list.
- [x] Add `make tf-check`, CI workflow, and run only fmt/init-backend=false/validate plus optional static security checks; never plan/apply or use AWS credentials.

## Open
- [x] Run three normal 10k acceptance runs plus one kill/fault run; record measured browse/hold p99, error rate, and every failure honestly. Three normal runs passed invariants; the kill-9 attempt failed before a final loadgen record and is documented.
- [x] Complete production-grade crash recovery, tenant isolation, load shedding, priority handling, and the scripted PSP/DB/webhook/clock/DLQ chaos scenarios; remaining acceptance limitations are documented.

## Done
- [x] Initial reference implementation was rejected as insufficient; retained only as scaffolding
- [x] Milestone 1: real PostgreSQL schema/Alembic/SQLAlchemy/Redis compose foundation
- [x] Milestone 2: guarded inventory holds, reaper, and 200-way PostgreSQL race tests
- [x] Milestone 3: Idempotency-Key middleware and R1/R3 tests
- [x] Milestone 4: persistent orders/payments/webhooks/reconciliation and tickets/check-in
- [x] Milestone 5: transactional outbox, dispatcher, DLQ, admin APIs/CLI, refunds, recovery
- [x] Milestone 6: auth/tenancy, waiting room, rate limits, breakers, bulkheads, shutdown, observability
- [x] Milestone 7: compose verification, named R1-R16 tests, database invariant loadgen, chaos, final acceptance (failures recorded)
- [x] Write 001 data model and invariants spec; update specs index and TODO
- [x] Write 002 state machine and API spec; update specs index and TODO
- [x] Create project skeleton, settings, clock, faults, observability, store interfaces, migrations, and baseline tests
- [x] Implement inventory, holds, orders, idempotency, payments, webhooks, and tickets with tests
- [x] Implement outbox, DLQ, refunds, check-in, auth, admin, waiting room, and resilience controls with tests
- [x] Implement load generator, invariant checker, chaos runner, Makefile, compose, Dockerfile, and acceptance tests
- [x] Harden integration, run test/load/chaos, record measurements and final status, commit and push milestones
- [x] Deployment addendum: AWS Terraform and deployment documentation/static validation only
