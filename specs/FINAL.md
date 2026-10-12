# Final status

## Verified
- PostgreSQL 16 and Redis 7 started with Compose; Alembic reached `0005_refunds`.
- Async SQLAlchemy guarded inventory update passed a real 200-parallel-hold race on 10 seats, with reaper verification.
- PostgreSQL Idempotency-Key middleware passed replay, body mismatch, and concurrent R3 retry tests.
- Persistent checkout/order events/charges/webhooks/tickets/atomic scans/refunds passed integration tests.
- PostgreSQL outbox poison handling reached the dead-letter table; R16 test passed.
- Named tests exist for R1 through R16; `make test` passed with Ruff clean (latest focused run: 30 passed; full unit run: 25 passed).
- Terraform `make tf-check` passed using only `fmt`, `init -backend=false`, and `validate`. No AWS credentials, plan, apply, or resources were used.

## Acceptance failures and limits
- Earlier 10k runs failed with connection exhaustion/deadlocks and produced 328 ticketed/672 held; those failures remain recorded.
- The latest corrected 10k run passed database invariants: 1,000 sold, 1,000 ticketed, 0 held, 0 leaked holds, 0 duplicate ticket sets, and 1,000 successful charges. Its end-to-end p99 was 56,195.87 ms, far above the brief's browse/hold targets.
- Three normal 10k repeats and the fault-injection worker-kill run remain unverified.
- Browse/hold-specific p99, error rate, PSP failure injection, full chaos scenarios, ticket-set/ledger acceptance at 1,000 seats, and production crash convergence remain unverified.
- The code contains persistent adapters and controls, but full production-grade tenant isolation, worker orchestration, and all dependency failure paths still require hardening.

## Deployment

AWS Terraform is present under `infra/terraform/` for owner-controlled later deployment. It defines staging/prod network, ALB/ACM/WAF, ECS Fargate API/worker/outbox/migration tasks, ECR, RDS PostgreSQL 16, ElastiCache, Secrets Manager, IAM, autoscaling, OIDC placeholder, and CloudWatch alarms. Deployment instructions, rollback/destroy cautions, estimates, and unverified items are in `infra/README.md`.
