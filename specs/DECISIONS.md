2025-02-14 — PostgreSQL owns all correctness-critical state; Redis is limited to advisory admission, rate limits, short locks, and budgets.
2025-02-14 — Inventory uses guarded conditional updates/unique constraints, with domain mutation, order event, and outbox committed atomically.
2025-02-14 — The foundation uses FastAPI with async SQLAlchemy boundaries, strict settings, injectable time, named fault points, and request-correlated JSON errors.
2025-02-14 — The first commerce implementation keeps a concurrency-safe reference service for tests while the PostgreSQL persistence adapter remains a hardening milestone.
2025-02-14 — Async consumers use bounded retry attempts and promote poison work to a replayable, idempotent dead-letter queue rather than blocking later messages.
2025-02-14 — The acceptance harness is Python-only and exposes explicit load, invariant, and chaos commands through Make targets.
2025-02-14 — AWS infrastructure is Terraform-defined for owner-controlled later deployment; this session permits only fmt, backend-disabled init, and validate, never plan/apply or AWS credentials.
