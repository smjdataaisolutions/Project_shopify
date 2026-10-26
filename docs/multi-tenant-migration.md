# Multi-tenant database migration and rollback

## Read-only findings — 24 October 2026

Live Neon counts were 23 products, 32 variants, 2 locations, 39 inventory rows, 15
orders, 21 line items, and 1 sync-state row. The separate session database contained one
offline session for `test-store-martina.myshopify.com`.

The live schema had primary keys but no inter-table foreign keys. Preflight found zero
orphan variants, zero orphan line-item orders, and two inventory rows whose locations no
longer exist. The migration preserves those rows and adds the inventory/location FK as
`NOT VALID`, while enforcing it for new writes.

## Migration behavior

`migrations/analytics/001_multi_tenant.up.sql`:

1. Creates `shops` and registers the development store.
2. Adds nullable `shop_id` and backfills every current row.
3. Aborts if any row is unowned.
4. Replaces global keys with tenant-aware composite keys.
5. Adds tenant/composite foreign keys and tenant-first indexes.

The runner verifies the database name, requires a backup/branch reference and `--apply`,
takes an advisory lock, runs transactionally, and records a checksum.

## PowerShell rehearsal

Use a disposable Neon branch or isolated PostgreSQL database, never live Neon:

```powershell
$env:MT_MIGRATION_DATABASE_URL = '<DISPOSABLE_DATABASE_URL>'

& '.\.venv\Scripts\python.exe' scripts\apply_analytics_migration.py `
  --expected-database '<DATABASE_NAME>' `
  --backup-reference '<BRANCH_OR_BACKUP_ID>'

& '.\.venv\Scripts\python.exe' scripts\apply_analytics_migration.py `
  --expected-database '<DATABASE_NAME>' `
  --backup-reference '<BRANCH_OR_BACKUP_ID>' `
  --apply

& '.\.venv\Scripts\python.exe' scripts\verify_multi_tenant_migration.py `
  --expected-database '<DATABASE_NAME>'

Remove-Item Env:MT_MIGRATION_DATABASE_URL
```

## Rehearsal result

Migration passed on disposable local database `shopify_ai_mt001_test`. Development-copy
counts remained 23/32/2/39/13/19/1. Composite product and order relationships validated;
the inventory/location constraint remained expectedly unvalidated. Six PostgreSQL tests
proved isolation using synthetic Fashion and Beauty tenants with reused Shopify IDs.

On 26 October 2026, the migration also passed on disposable Neon branch
`mt001-rehearsal-2026-10-26`, database `neondb`, using snapshot
`pre-mt001-2026-10-26 04:21:11 UTC (manual)` as the recovery reference. The recorded
migration checksum is
`4594d8b05343cef03e6ce5cedfc79788aecfb61dd11a7af187089067be48225a`.

The live-copy counts remained 23/32/2/39/15/21/1, all rows were assigned to
`test-store-martina.myshopify.com`, and no null tenant ownership, orphan variants, or
orphan line-item orders were found. Eleven tenant constraints and seven tenant-first
indexes were present. Reapplying the migration returned `already_applied=true`.
Fifteen read-only PostgreSQL regression tests passed across Overview, Sales, Inventory,
Orders, and Products.

The two preserved inventory rows belong to deleted location `Snow City Warehouse` and
cannot be safely reassigned to an active location. They remain accepted historical rows;
the inventory/location constraint is `NOT VALID` for those rows and enforced for new
writes.

## Rollback

Before a second tenant is onboarded, `001_multi_tenant.down.sql` can reverse the schema;
it refuses if more than the development tenant exists. After multi-store data exists,
never remove tenant ownership. Restore the pre-migration Neon branch/backup or roll
forward, then route Cloud Run traffic to compatible revisions.

No live migration or rollback is authorized by this document.
