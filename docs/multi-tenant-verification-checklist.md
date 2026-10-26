# MT-001 verification checklist

## Completed locally

- [x] Shopify ID-token validation accepts canonical installed shops.
- [x] Forged, expired and mismatched tenant assertions are rejected.
- [x] Missing authentication/assertion returns 401; tenant mismatch returns 403.
- [x] Registration is idempotent; a new shop receives empty analytics.
- [x] All seven tables isolate two tenants using reused Shopify IDs.
- [x] Cross-tenant joins return no rows.
- [x] Webhook upserts/deletes cannot modify another tenant.
- [x] Overview, Sales, Inventory, Orders and Products run under tenant scope.
- [x] Backend regression suite passes.
- [x] Frontend regression suite and production build pass.
- [x] Deployment scripts remain preview-only by default with min 0/max 1.

## Required before live migration/deployment

- [x] Record snapshot `pre-mt001-2026-10-26 04:21:11 UTC (manual)`.
- [x] Rehearse on disposable branch `mt001-rehearsal-2026-10-26`.
- [x] Preserve the expected live baseline: 23/32/2/39/15/21/1.
- [x] Pass 15 read-only regression tests across all five analytics modules.
- [x] Accept two historical rows for deleted location `Snow City Warehouse`; do not remap them.
- [x] Create tenant-assertion secret version 1 and grant accessor only to both runtime service accounts.
- [ ] Obtain approval for live migration, IAM, and both deployments.
- [ ] Verify FastAPI remains IAM-private with no `allUsers` binding.
- [ ] Test the development store, then a separate authorized test store.
- [ ] Observe authorization, tenant-scope and database logs before beta onboarding.
