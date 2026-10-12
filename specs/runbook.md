# Operations runbook

- **PSP outage:** pause sales, preserve awaiting-payment orders, let bounded retries expire, reconcile provider state before retrying charges.
- **Database failover:** mark readiness false, stop mutations, restore primary, run hold reaper and stuck-order recovery, then resume admission.
- **Stuck holds:** inspect expired holds, run the reaper, and verify `sold + held <= capacity` before reopening sales.
- **DLQ growth:** inspect origin/error history and age, fix the consumer, replay one message, verify idempotence, then bulk replay; discard only with an operator reason.
- **Latency/load failure:** pause sales and reduce admission. The load results file is authoritative; do not infer acceptance from HTTP completion alone.
