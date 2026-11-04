# Public distribution readiness

Status: the existing `review-ready-v1` Shopify configuration and custom domain are
active. The compliance implementation and migration described below remain local:
they have not been deployed, migrated to Neon, committed, pushed, or submitted for
App Store review.

## Implemented locally

- Declared all mandatory compliance topics in both Shopify TOML configurations:
  `customers/data_request`, `customers/redact`, and `shop/redact`.
- Added a fixed `/webhooks/compliance` React Router action that authenticates the
  Shopify webhook before forwarding it to the IAM-private FastAPI service.
- Preserved the original body and HMAC, added the short-lived signed tenant
  assertion, and used the fixed private `/internal/shopify-compliance` destination.
- FastAPI independently verifies the tenant assertion, Shopify HMAC, payload shop,
  allowlisted topic, and JSON body.
- `customers/data_request` is recorded idempotently in a tenant-scoped,
  PII-minimized fulfillment queue. Only Shopify's request ID and requested order
  IDs are retained; customer email, phone, and the raw webhook are not stored.
- `customers/redact` deletes only the authenticated tenant's requested order and
  line-item records.
- `shop/redact` deletes all seven analytics datasets and the shop tenant record in
  foreign-key-safe order. Missing shops are acknowledged idempotently.
- A successful `shop/redact` also removes persistent Shopify sessions for that shop.
- Added migration `002_shopify_compliance_requests` and an operator-only export
  workflow. The migration has not been applied to Neon.
- Removed unused template write scopes and demo metaobject definitions. The prepared
  least-privilege scopes are `read_inventory`, `read_locations`, `read_orders`, and
  `read_products`.
- Replaced placeholder application and redirect URLs in the default Shopify TOML
  with the deployed frontend URL.

## Validation completed

- Frontend unit tests: 94 passed.
- Backend regression suite: 245 tests run successfully; 24 were intentionally
  skipped when optional PostgreSQL-backed suites were not explicitly enabled.
- Frontend TypeScript check: passed.
- Frontend ESLint: passed after importing Node's `Buffer` in its existing test.
- Frontend production build: passed and emitted the compliance route.
- Both Shopify TOML files parse successfully.
- Targeted tests cover valid HMAC, invalid HMAC returning 401, cross-tenant assertion
  rejection, payload-shop mismatch, tenant-scoped order redaction, full shop
  redaction, PII-minimized data-request intake, migration invariants, idempotency,
  and topic allowlisting.
- Migration SQL has been reviewed and its guarded runner accepts an explicit
  version.

## Local PostgreSQL rehearsal — 4 November 2026

Migration `002_shopify_compliance_requests` was rehearsed on disposable local database
`shopify_ai_compliance_rehearsal_20261104`, cloned from the original seven-table
`shopify_ai` database. No Neon branch or production database was used.

- Migration 001 reproduced the multi-tenant baseline with counts 23 products, 32
  variants, 2 locations, 39 inventory rows, 13 orders, 19 line items, and 1 sync row.
- Migration 002 dry-run and apply passed with checksum
  `736ecc90422f3a2765b7fb15846f4a335a7f124790ddf5f134dbca467f121299`.
- Duplicate delivery of one synthetic data request produced one queue record.
- The export contained one order and two line items and contained no customer email
  field. Completion removed the request from the open queue.
- Reapplication returned `already_applied=true`.
- Down migration and subsequent up migration both passed.
- Final verification found zero invalid tenant references, zero malformed order-ID
  documents, an empty queue, and unchanged analytics counts.
- The disposable local database remains available for review. It is not used by the
  application or any Cloud Run service.

## Neon branch rehearsal — 4 November 2026

Migration `002_shopify_compliance_requests` was also rehearsed on Neon branch
`compliance-rehearsal-2026-11-04`. Its endpoint was verified as different from the
production endpoint before any write.

- The branch contained both tenants: `test-store-martina.myshopify.com` and
  `jerin-clothing.myshopify.com`.
- Pre-migration state contained migration 001 and no compliance table.
- Migration 002 dry-run and application passed with the reviewed checksum.
- Verification returned zero invalid tenant references and zero malformed order-ID
  documents.
- A duplicate synthetic request produced one row inside a transaction; the transaction
  was rolled back and zero queue rows persisted.
- Reapplication returned `already_applied=true`.
- Final analytics counts remained 43 products, 193 variants, 3 locations, 200 inventory
  rows, 18 orders, 25 line items, and 2 sync-state rows.
- Production Neon was not connected through the rehearsal URL and was not modified.

## Blockers before App Store submission

1. Rehearse, approve, and apply migration `002_shopify_compliance_requests`, then
   deploy the compliance build and test valid and invalid webhook deliveries.
2. Review protected customer data access for `read_orders` in the Dev Dashboard and
   complete Shopify's request or opt-out decision accurately.
3. Run dependency remediation planning. The read-only production dependency audit
   reports four high and two moderate advisories, none critical. Suggested automated
   fixes require breaking/incompatible package changes and were not applied.
4. Provide and verify the public privacy policy, terms of service, support URL,
   support email, emergency developer contact, pricing/billing configuration, app
   icon, screenshots, listing text, and reviewer instructions.
5. Test install, reinstall, uninstall, automatic initial synchronization, webhook
   delivery, compliance webhooks, empty state, and failure recovery on authorized
   development stores.
6. Review and approve the access-scope change. Releasing it can require merchants to
   approve the updated scope set.

## Customer data-request runbook

Shopify requires a 2xx acknowledgement and completion within 30 days. The queue's
`due_at` records that deadline. Use a secured operator workstation; never place an
export in the repository, Cloud Run logs, email, or a public file share.

Check the queue at least daily. This output contains no customer contact details or
analytics records:

```powershell
$env:SHOPIFY_COMPLIANCE_DATABASE_URL = '<Neon pooled connection string>'
.\.venv\Scripts\python.exe .\scripts\fulfill_shopify_data_request.py list
```

```powershell
.\.venv\Scripts\python.exe .\scripts\fulfill_shopify_data_request.py export `
  --shop-domain 'merchant.myshopify.com' `
  --request-id '<Shopify data_request.id>' `
  --output 'D:\SecureExports\request.json'
```

Review the export and deliver it through an authenticated, access-controlled channel
to the requesting store owner. Only after confirmed delivery, record completion:

```powershell
.\.venv\Scripts\python.exe .\scripts\fulfill_shopify_data_request.py complete `
  --shop-domain 'merchant.myshopify.com' `
  --request-id '<Shopify data_request.id>'
Remove-Item -LiteralPath 'D:\SecureExports\request.json'
```

The final deletion is intentionally manual so the exact reviewed export path is
visible. Do not mark a request complete before delivery. The export contains only
analytics fields already stored by OneStop Analytics; the app does not store customer
email, phone, billing address, or shipping address.

## Release sequence after separate approval

1. Resolve the blockers above and rerun all tests and security checks.
2. Build review-tagged frontend and backend images without changing live traffic.
3. Apply the reviewed analytics migration before deploying code that writes to its
   queue. Use `--version 002_shopify_compliance_requests` with the guarded migration
   runner and verify the SQL on an isolated Neon branch first.
4. Deploy the reviewed images while preserving backend IAM privacy and scaling.
5. Release the reviewed Shopify TOML configuration so Shopify registers compliance
   subscriptions only after the receiving code and queue are available.
6. Trigger test compliance webhooks and verify valid 2xx and invalid-HMAC 401
   responses in Cloud Run logs without logging payload PII.
7. Only then complete automated checks and submit the App Store listing for review.

## Rollback

- Before migration, create or verify a recoverable Neon snapshot/branch and record
  its identifier in the guarded migration command.
- If application behavior fails after deployment, route both Cloud Run services back
  to their previous known-good revisions. Keep the new table in place; it is additive
  and does not alter the seven analytics tables.
- Do not run the down migration after any privacy request has been received unless
  its queue records have been securely preserved and every request is accounted for.
- If the migration itself fails, PostgreSQL rolls it back transactionally. Investigate
  on the rehearsal branch before retrying; do not reset or recreate Neon.
