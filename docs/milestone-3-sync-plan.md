# Milestone 3 synchronization requirements

MT-001 prepares tenant-aware ingestion but does not deploy jobs, schedules, queues, or
full background synchronization infrastructure.

Milestone 3 should:

1. Trigger an initial full sync per new shop using only that shop's offline session.
2. Queue immutable `shop_id`, never credentials or tokens.
3. Use per-shop locks, cursors, retries and idempotency keys.
4. Keep sync data-only; schema changes use reviewed migrations.
5. Register and monitor required webhooks per installation.
6. Reconcile webhook gaps using per-shop sync state.
7. Define uninstall retention and mandatory privacy webhook handling.
8. Add rate-limit handling, failure visibility and cost limits before beta.

Cloud Run Jobs, Scheduler, Pub/Sub or other billable resources require separate design
and explicit approval.
