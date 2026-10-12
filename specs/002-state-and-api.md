# 002 State machine and API

## Order state machine
The only transition entry point is `OrderService.transition(order_id, target, reason)`, in a database transaction. It appends one `order_events` row and emits required outbox work.

| From | Allowed targets |
|---|---|
| pending | awaiting_payment, failed, expired, cancelled |
| awaiting_payment | paid, failed, expired, cancelled |
| paid | ticketed, refunded, cancelled |
| ticketed | refunded, cancelled |
| failed | pending |
| expired | pending |
| cancelled | refunded |
| refunded | — |

Webhook and recovery handlers may request a transition but cannot bypass the table. Stale PSP events are durably recorded and acknowledged without changing state.

## Public API
All mutating operations require `Idempotency-Key`; request bodies are strict Pydantic models and responses include `X-Request-ID`. Auth scopes are organizer/admin or buyer session as appropriate.

- `GET /healthz`, `GET /readyz`, `GET /metrics`
- `GET /events`, `GET /events/{event_id}`, `GET /events/{event_id}/inventory`
- `POST /events/{event_id}/holds` — reserve seats or quantity with TTL; returns hold expiry.
- `POST /holds/{hold_id}/checkout` — creates an awaiting-payment order; only active holds accepted.
- `POST /orders/{order_id}/pay` — idempotent PSP charge request; returns pending/paid terminal-safe status.
- `GET /orders/{order_id}` — buyer-visible terminal state and retry-safe polling.
- `POST /webhooks/{provider}` — signed PSP event; durable dedupe before response.
- `POST /orders/{order_id}/refunds` — full or partial idempotent refund.
- `GET /orders/{order_id}/tickets`, `POST /tickets/{ticket_id}/resend`, `POST /tickets/{ticket_id}/transfer`
- `POST /tickets/{ticket_id}/scan` — online atomic one-time use; signed payload supports offline verification.
- `POST /waiting-room/{event_id}/admit`, `GET /waiting-room/{event_id}/position`
- Organizer/admin: `GET /admin/events/{event_id}/dashboard`, `GET /admin/events/{event_id}/inventory`, `POST /admin/holds/{hold_id}/release`, `POST /admin/events/{event_id}/pause`.
- Admin DLQ: `GET /admin/dead-letters`, `GET /admin/dead-letters/{id}`, `POST /admin/dead-letters/{id}/replay`, `POST /admin/dead-letters/replay`, `POST /admin/dead-letters/{id}/discard`.

## Error contract
Errors are JSON `{code, message, request_id, retry_after_seconds?}`. `422` means invalid input or idempotency body mismatch; `401/403` auth; `404` missing or tenant-invisible resource; `409` state/conflict or in-flight idempotency; `429/503` bounded overload with `Retry-After`; `500` is sanitized and request-correlated. PSP webhooks return 2xx after durable receipt even when processing is deferred.

## Reliability behavior
Idempotency lookup occurs before domain work. A matching completed key replays its exact status/body; a mismatched body is `422`; an in-flight duplicate waits briefly or returns `409` with `Retry-After`. Timeouts and cancellation are bounded at HTTP and dependency boundaries. Recovery jobs sweep expired holds, stuck orders, outbox retries, webhook discrepancies, and DLQ work.
