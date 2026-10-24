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

- [ ] Verify and record a recoverable Neon backup.
- [ ] Rehearse on a disposable Neon branch.
- [ ] Compare the expected live baseline: 23/32/2/39/15/21/1.
- [ ] Compare representative KPIs for all five modules.
- [ ] Resolve or explicitly accept two historical inventory/location orphans.
- [ ] Create and permission the tenant-assertion secret.
- [ ] Obtain approval for live migration, IAM, and both deployments.
- [ ] Verify FastAPI remains IAM-private with no `allUsers` binding.
- [ ] Test the development store, then a separate authorized test store.
- [ ] Observe authorization, tenant-scope and database logs before beta onboarding.
