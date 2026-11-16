# APP-REVIEW-001 controlled production release

Date: 5 November 2026

Status: **BACKEND RELEASE REMAINS BLOCKED.** The explicitly authorized frontend-only
App Bridge and installation-flow corrections were deployed on 16 November 2026.
No backend deployment, production migration, IAM change, Shopify version release,
secret rotation, or Git push was performed.

## Release gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Disposable PostgreSQL environment | PASS | PostgreSQL 18 cluster bound only to `127.0.0.1:55433`; no Neon connection used |
| Migration 003 | PASS | Guarded up, idempotent up, down, re-up, and verify SQL all passed; checksum `90c2570a0d8acfeb677cbd393042187c39242b1a7fee89e4d902b32a853ae38f` |
| Single-store analytics/privacy integration | PASS | 33 selected tests passed on a fresh single-store rehearsal database |
| Initial sync and two-store isolation | PASS | 8 PostgreSQL tests passed on a separate multi-store rehearsal database |
| Retry behavior | PASS | Five fresh leases, retry counts 1–5, terminal failure at five, and unaffected completed tenant verified |
| Privacy service and HMAC | PASS locally | 13 tests passed, including valid HMAC, data-request minimization/idempotency, customer redaction isolation, and shop redaction isolation |
| Cloud Run configuration compatibility | PASS by configuration | Active service identity, port, CPU, memory, concurrency, timeout, ingress, environment names, and secret names match the proposed configuration |
| Frontend Cloud Run image/revision | PASS | Corrected image `smj-shopify-frontend@sha256:f50e52c6ab4c2cbc73fcaff72ac70c86535adbf1ccad9040527f1b8d39d6cf7c` passed all frontend gates and final image/SBOM scans; revision `smj-shopify-frontend-00018-wod` is Ready and receives 100% traffic |
| Backend runtime dependencies | **FAIL** | `pip-audit` found 27 advisories: `certifi 2026.7.22`, actively used `PyJWT 2.10.1`, and `urllib3 2.7.0` |
| Frontend runtime dependencies | PASS | Clean `npm ci` followed by `npm audit --omit=dev` found zero vulnerabilities; final Trivy 0.76.2 image scan found zero critical, high, or medium findings |
| Free Beta selection | PASS (manual) | Operator confirmed the three pending billing checks: zero-cost Free Beta, no charge approval, and no paid plan switching |
| Clean Shopify installation | NEEDS VERIFICATION | Deployed HTTP behavior is correct, but authenticated Shopify Admin installation/navigation could not be rerun because browser automation was unavailable |
| Valid live privacy delivery | NEEDS VERIFICATION | Only local/database and invalid-production-HMAC paths were exercised; use the safe procedure below |

The initial combined PostgreSQL run was intentionally not accepted as evidence. The
legacy analytics tests use an unscoped session and assume a one-shop fixture, so they
produce duplicate/global aggregates if run after multi-store tests in the same
database. All opt-in paths were rerun in fresh databases matching their documented
topology. Any future CI job must preserve this separation or migrate the legacy tests
to an explicitly tenant-scoped session.

## Security remediation required before any release

Backend lockfile minimums to review and update:

- `certifi`: current `2026.7.22`; use at least `2026.10.18`.
- `PyJWT`: current `2.10.1`; use at least `2.15.0`. This package verifies Shopify
  session tokens and tenant assertions, so it is runtime-reachable.
- `urllib3`: current `2.7.0`; use at least `2.8.0`.

After updating and regenerating the reviewed lockfile, run:

```powershell
$auditVenv = Join-Path $env:TEMP 'onestop-pip-audit-release'
& $auditVenv\Scripts\python.exe -m pip_audit -r requirements.lock.txt --progress-spinner off
$env:DATABASE_URL = 'postgresql+psycopg://postgres@127.0.0.1:55433/onestop_rehearsal_tenant_20261105'
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
Remove-Item Env:DATABASE_URL
```

Frontend remediation requires a reviewed dependency change rather than accepting the
Dockerfile deletion as the only control:

1. Move build-only React Router packages, including `@react-router/dev` and
   `@react-router/fs-routes`, out of production dependencies after confirming the
   server bundle does not import them.
2. Upgrade Prisma/session-storage compatibility or otherwise remove
   `prisma -> @prisma/config -> deepmerge-ts` from the runtime dependency graph.
3. Do not use the audit suggestion to downgrade session storage without a separate
   compatibility review.
4. Build the final image and scan its filesystem/SBOM. Require zero critical/high
   findings and an approved disposition for every moderate finding.

Frontend remediation completed on 16 November 2026:

- Kept the Shopify-supported Prisma compatibility set at
  `@shopify/shopify-app-session-storage-prisma 9.0.1`, `prisma 6.19.3`, and
  `@prisma/client 6.19.3`.
- Overrode only `deepmerge-ts` from vulnerable `7.1.5` to patched `8.0.2`.
  Prisma's config package imports only the stable `deepmerge` function for its c12
  merger; schema validation, client generation, recursive-graph handling, and the
  Shopify session CRUD/refresh-token compatibility test all passed.
- `npm audit --omit=dev` reports zero vulnerabilities after a clean install.
- The final runtime removes unused global npm/npx tooling, invokes
  `@react-router/serve` directly, and upgrades runtime zlib to `1.4-r0`.
- Final image:
  `us-east5-docker.pkg.dev/smj-shopify-analytics/smj-shopify-api/smj-shopify-frontend@sha256:0b03ef157d66282a09fbb8cbddced8482b3b04ae2b964eb6917198d17a3b4e1e`.
- Trivy 0.76.2 found zero critical, high, or medium findings across Alpine and
  Node packages. The generated CycloneDX SBOM was 235,313 bytes with SHA-256
  `902ec1d71e31bf6eff8641664823f2b14c0c5139a4bbf3faede5993ec7c1e5d2`.
- No deployment, Cloud Run revision, traffic change, migration, commit, push, or
  Shopify submission was performed.

### Frontend installation-flow corrective release (16 November 2026)

- Isolated release context:
  `release-contexts/one-stop-analytics-appbridge-security-install-20261116-02`.
  Relative to the prior scanned frontend context, source changes were limited to
  `app/routes/auth.login/route.jsx` plus the focused
  `tests/shopifyInstallFlow.test.js` regression coverage.
- The route still calls Shopify React Router's `login(request)` in its loader. A
  valid Shopify shop context returned `302` directly to
  `https://admin.shopify.com/store/<handle>/oauth/install`; missing or invalid
  external context rendered non-looping Shopify-owned-surface guidance with no
  form, shop input, or `.myshopify.com` prompt.
- Clean `npm ci`, `npm audit --omit=dev`, 4 focused installation/session tests,
  98 full frontend tests, typecheck, lint, and production build all passed.
- Image build `a415f646-719a-4e6b-b45f-ff4369add5a7` produced immutable digest
  `sha256:f50e52c6ab4c2cbc73fcaff72ac70c86535adbf1ccad9040527f1b8d39d6cf7c`.
- Exact-image runtime check `1601432c-d6ab-4fd5-9a3a-d87d9114d7d2` confirmed the
  corrected bundle markers, absence of the legacy form markers, and `302 /app`.
- Trivy 0.76.2 build `78893d32-30d7-43d3-8ade-e6d81b6c2850` found zero critical,
  high, or medium vulnerabilities. The CycloneDX SBOM is 235,313 bytes with
  SHA-256 `af295a7498cff22107ebe373e146b9f0acbee58e289aebb640a362e09acae715`.
- Zero-traffic revision `smj-shopify-frontend-00018-wod` became Ready before
  promotion. Environment, secret references, service account, ingress, resources,
  scaling, frontend IAM, and private-backend IAM fingerprints matched the baseline.
- Production traffic is 100% on `smj-shopify-frontend-00018-wod`; rollback target
  `smj-shopify-frontend-00015-xob` remains available. No rollback was required.
- Requirements 2.3.1 and 2.3.2 are likely passing by exact-source, exact-image,
  deployed HTTP, and OAuth-redirect evidence. Authenticated Shopify Admin browser
  installation and navigation remain a manual verification item.
- Shopify AI Toolkit review of the exact released source/image reported 31 likely
  passing requirements, zero likely failing, zero needing review, and 10 correctly
  skipped category-specific groups.

Required commands after remediation:

```powershell
Push-Location one-stop-analytics
& 'C:\Program Files\nodejs\npm.cmd' ci
& 'C:\Program Files\nodejs\npm.cmd' test
& 'C:\Program Files\nodejs\npm.cmd' run typecheck
& 'C:\Program Files\nodejs\npm.cmd' run lint
& 'C:\Program Files\nodejs\npm.cmd' run build
& 'C:\Program Files\nodejs\npm.cmd' audit --omit=dev
Pop-Location
```

## Active/proposed revision compatibility

Active revisions:

- API: `smj-shopify-api-00008-dvx`, image digest
  `sha256:faf30146850a512b69041d778f948d1a8209dce6f7ed89c1150f22557a8f75c8`.
- Frontend: `smj-shopify-frontend-00018-wod`, image digest
  `sha256:f50e52c6ab4c2cbc73fcaff72ac70c86535adbf1ccad9040527f1b8d39d6cf7c`.

Both use the expected runtime service accounts, port 8080, one CPU, 512 MiB,
concurrency 8, 60-second timeout, maximum one instance, and ingress `all`. The API
remains IAM-private through its existing invoker policy; ingress `all` does not grant
unauthenticated invocation.

Compatibility ordering:

1. Migration 003 is additive; active revisions ignore it.
2. The proposed API adds endpoints and remains compatible with the active frontend.
3. The proposed frontend requires the proposed API initial-sync endpoints.
4. Therefore migrate, deploy/test API, promote API, then deploy/test/promote frontend.
5. Roll back frontend traffic first, then API traffic. Leave migration 003 applied.

## Approval-gated production commands

These commands are prepared only. Do not run them until dependency security passes,
a recoverable Neon branch/snapshot identifier exists, immutable image digests have
been recorded, and explicit production approval is given.

### 1. Operator variables and read-only capture

```powershell
$gcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
$project = 'smj-shopify-analytics'
$region = 'us-east5'
$apiService = 'smj-shopify-api'
$frontendService = 'smj-shopify-frontend'
$oldApiRevision = 'smj-shopify-api-00008-dvx'
$oldFrontendRevision = 'smj-shopify-frontend-00018-wod'
$release = 'app-review-001-20261105'
$backupReference = '<APPROVED_NEON_BRANCH_OR_SNAPSHOT_ID>'

& $gcloud run services describe $apiService --project=$project --region=$region --format=export
& $gcloud run services describe $frontendService --project=$project --region=$region --format=export
& $gcloud run services get-iam-policy $apiService --project=$project --region=$region
& $gcloud run services get-iam-policy $frontendService --project=$project --region=$region
```

### 2. Build immutable images

```powershell
$apiImage = "us-east5-docker.pkg.dev/$project/smj-shopify-api/smj-shopify-api:$release"
$frontendImage = "us-east5-docker.pkg.dev/$project/smj-shopify-api/smj-shopify-frontend:$release"

& $gcloud builds submit . --project=$project --region=$region --tag=$apiImage
Push-Location one-stop-analytics
& $gcloud builds submit . --project=$project --region=$region --tag=$frontendImage
Pop-Location

& $gcloud artifacts docker images describe $apiImage --project=$project --format='value(image_summary.digest)'
& $gcloud artifacts docker images describe $frontendImage --project=$project --format='value(image_summary.digest)'
```

Replace the tags below with the recorded `@sha256:...` image references before
deployment.

### 3. Guarded migration 003

```powershell
$env:MT_MIGRATION_DATABASE_URL = & $gcloud secrets versions access 3 `
  --secret='smj-shopify-neon-database-url' --project=$project

& .\.venv\Scripts\python.exe scripts\apply_analytics_migration.py `
  --version 003_shopify_initial_sync_jobs `
  --expected-database neondb `
  --backup-reference $backupReference

# Approval checkpoint: review database, checksum, and backup reference.
& .\.venv\Scripts\python.exe scripts\apply_analytics_migration.py `
  --version 003_shopify_initial_sync_jobs `
  --expected-database neondb `
  --backup-reference $backupReference `
  --apply

& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' `
  --dbname=$env:MT_MIGRATION_DATABASE_URL -X -v ON_ERROR_STOP=1 `
  -f migrations\analytics\003_shopify_initial_sync_jobs.verify.sql

Remove-Item Env:MT_MIGRATION_DATABASE_URL
```

Every `failures` value must be zero. Do not run the down migration during a normal
application rollback.

### 4. Deploy API with zero traffic

```powershell
& $gcloud run deploy $apiService `
  --project=$project --region=$region --platform=managed `
  --image='<API_IMAGE_AT_SHA256>' `
  --service-account='smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com' `
  --set-secrets='DATABASE_URL=smj-shopify-neon-database-url:3,SHOPIFY_API_SECRET=smj-shopify-app-api-secret:5,TENANT_ASSERTION_SECRET=smj-shopify-tenant-assertion-secret:2' `
  --set-env-vars='APP_NAME=SMJ Shopify Analytics API - Staging,DEPLOYMENT_ENVIRONMENT=staging,API_DOCS_ENABLED=false,API_AUTH_ENABLED=true,SHOPIFY_API_KEY=38254bd587274d5002c06d0ecab16259,TENANT_ASSERTION_ISSUER=smj-shopify-frontend,TENANT_ASSERTION_AUDIENCE=smj-shopify-api,DATABASE_POOL_SIZE=2,DATABASE_MAX_OVERFLOW=2,DATABASE_POOL_TIMEOUT_SECONDS=10,DATABASE_POOL_RECYCLE_SECONDS=300' `
  --port=8080 --cpu=1 --memory=512Mi --concurrency=8 --timeout=60s `
  --min-instances=0 --max-instances=1 --cpu-throttling --no-cpu-boost `
  --execution-environment=gen2 --ingress=all `
  --no-traffic --tag=review-api --quiet
```

Do not add any IAM binding. Resolve the tagged URL and test it with an identity token:

```powershell
$api = (& $gcloud run services describe $apiService --project=$project --region=$region --format=json) | ConvertFrom-Json
$apiTagUrl = ($api.status.traffic | Where-Object tag -eq 'review-api').url
$apiAudience = $api.status.url
$apiToken = & $gcloud auth print-identity-token --audiences=$apiAudience
curl.exe --fail-with-body -H "Authorization: Bearer $apiToken" "$apiTagUrl/health"
curl.exe --fail-with-body -H "Authorization: Bearer $apiToken" "$apiTagUrl/health/ready"
Remove-Variable apiToken
```

Then promote the exact new API revision only after smoke tests pass:

```powershell
$newApiRevision = (& $gcloud run services describe $apiService --project=$project --region=$region --format='value(status.latestReadyRevisionName)')
& $gcloud run services update-traffic $apiService --project=$project --region=$region --to-revisions="$newApiRevision=100"
```

### 5. Deploy frontend with zero traffic

```powershell
$backendUrl = (& $gcloud run services describe $apiService --project=$project --region=$region --format='value(status.url)')
$frontendEnvFile = Join-Path $env:TEMP 'onestop-release-frontend-env.json'
[ordered]@{
  SHOPIFY_API_KEY = '38254bd587274d5002c06d0ecab16259'
  SHOPIFY_APP_URL = 'https://app.smjdataai.com'
  SCOPES = 'read_inventory,read_locations,read_orders,read_products'
  TENANT_ASSERTION_ISSUER = 'smj-shopify-frontend'
  TENANT_ASSERTION_AUDIENCE = 'smj-shopify-api'
  FASTAPI_BASE_URL = $backendUrl
  FASTAPI_AUDIENCE = $backendUrl
  FASTAPI_IAM_AUTH_ENABLED = 'true'
  DEPLOYMENT_ENVIRONMENT = 'staging'
} | ConvertTo-Json | Set-Content -LiteralPath $frontendEnvFile -Encoding utf8
try {
  & $gcloud run deploy $frontendService `
    --project=$project --region=$region --platform=managed `
    --image='<FRONTEND_IMAGE_AT_SHA256>' `
    --service-account='smj-shopify-frontend-runner@smj-shopify-analytics.iam.gserviceaccount.com' `
    --set-secrets='SHOPIFY_API_SECRET=smj-shopify-app-api-secret:5,DATABASE_URL=smj-shopify-session-database-url:2,TENANT_ASSERTION_SECRET=smj-shopify-tenant-assertion-secret:2' `
    --env-vars-file=$frontendEnvFile `
    --port=8080 --cpu=1 --memory=512Mi --concurrency=8 --timeout=60s `
    --min-instances=0 --max-instances=1 --cpu-throttling --no-cpu-boost `
    --execution-environment=gen2 --ingress=all `
    --no-traffic --tag=review-frontend --quiet
}
finally {
  Remove-Item -LiteralPath $frontendEnvFile -Force -ErrorAction SilentlyContinue
}

$frontend = (& $gcloud run services describe $frontendService --project=$project --region=$region --format=json) | ConvertFrom-Json
$frontendTagUrl = ($frontend.status.traffic | Where-Object tag -eq 'review-frontend').url
curl.exe --fail-with-body "$frontendTagUrl/"
```

The tagged URL cannot complete Shopify OAuth because the approved callback remains the
custom production hostname. Promote only after the static/root smoke test and then run
the clean-store checklist through `https://app.smjdataai.com`.

```powershell
$newFrontendRevision = (& $gcloud run services describe $frontendService --project=$project --region=$region --format='value(status.latestReadyRevisionName)')
& $gcloud run services update-traffic $frontendService --project=$project --region=$region --to-revisions="$newFrontendRevision=100"
```

No `shopify app deploy` is required if the reviewed `shopify.app.toml` is byte-for-byte
equivalent to active version `compliance-ready-v2`. If it differs, stop and request a
separate Shopify-version approval.

## Smoke tests after traffic promotion

- Existing installed shop opens with App Bridge/session-token authentication.
- Backend remains anonymous-deny/IAM-private.
- Existing dashboards and incremental webhooks remain functional.
- Clean development-store install creates one tenant and one initial job.
- Initial status advances pending -> running -> completed; close/reopen resumes from
  the saved resource/cursor.
- Product, variant, location, inventory, order, and line-item counts reconcile with
  Shopify; no completed job has orphan references.
- Repeated enqueue/page delivery creates no duplicate composite keys.
- A controlled throttling/failure test increments retry without changing another
  tenant.
- No access token, authorization header, customer email, or phone appears in database
  job metadata or logs.

## Rollback commands

Rollback frontend first so the proposed frontend never calls an old API:

```powershell
& $gcloud run services update-traffic $frontendService --project=$project --region=$region --to-revisions="$oldFrontendRevision=100"
& $gcloud run services update-traffic $apiService --project=$project --region=$region --to-revisions="$oldApiRevision=100"
```

Keep migrations 002 and 003 applied. Migration 003 is additive and inert to the old
revisions. Consider its down migration only in a separate maintenance window after
zero pending/running jobs, expired leases, reconciliation, and a new backup.

## Free Beta and clean-install checklist

- [ ] In App pricing, confirm the public plan name is exactly **Free Beta**.
- [ ] Confirm recurring price is `$0`, usage charges/meters are absent, and no trial
      expiry converts it to a charge.
- [ ] Confirm the public listing says free and does not advertise a conflicting price.
- [ ] Use a new development store owned by the same Partner organization.
- [ ] Begin installation from Dev Dashboard/Shopify Admin/App Store, never by typing a
      domain into the app.
- [ ] Confirm requested scopes are only inventory, locations, orders, and products.
- [ ] Confirm OAuth returns to the embedded app and creates an offline session.
- [ ] Open Shopify's hosted plan page at
      `https://admin.shopify.com/store/<store_handle>/charges/<app_handle>/pricing_plans`.
- [ ] Select Free Beta; confirm no payment method or non-zero approval is requested.
- [ ] Confirm the welcome redirect returns to `/app` and any `plan_handle` is accepted
      without an access loop.
- [ ] Confirm every dashboard is available while initial synchronization is pending.
- [ ] Close the tab mid-sync, reopen it, and confirm safe resume.
- [ ] Uninstall, verify only the development tenant/session is affected, reinstall,
      and confirm fresh OAuth plus idempotent sync.
- [ ] Repeat in incognito/third-party-cookie-restricted mode.

Shopify's current no-charge development-store behavior does not by itself prove that
the public plan is free; the Partner Dashboard price and usage configuration remain
the source of truth.

## Safe valid privacy-delivery procedure

Never test a redaction topic using a production merchant's domain or resource IDs.

1. Create a dedicated development store containing only synthetic products,
   customers, and orders with recorded IDs.
2. Install the app and let synchronization complete. Record the test `shop_id`, row
   counts, and a recoverable database branch/snapshot.
3. First use `shopify app webhook trigger` against an isolated staging/clone endpoint
   backed by a cloned analytics database. Shopify CLI payloads are fixed and are not
   retried; they test delivery/HMAC handling, not subscription configuration.
4. For a real end-to-end production-route test, use only the dedicated development
   store and perform the corresponding Shopify privacy action. Customer redaction can
   be delayed by ten days, and shop redaction is emitted no earlier than 48 hours
   after uninstall and is cancelled by reinstall.
5. Test in this order: `customers/data_request`, `customers/redact`, then
   `shop/redact` last.
6. After data request, verify only request/order identifiers were stored and no email
   or phone appears in rows or logs.
7. After customer redaction, verify only the synthetic requested orders/line items in
   the development tenant were removed; compare a second development tenant's counts.
8. Before shop redaction, take another snapshot and confirm the target domain twice.
   After delivery, verify only that tenant's privacy requests, sync jobs, analytics,
   sync state, shop row, and frontend sessions are gone.
9. Verify duplicate deliveries return 2xx and are idempotent. Preserve delivery IDs,
   timestamps, status codes, and count-only evidence; do not export PII.
10. Do not reinstall until the delayed shop-redaction delivery has been observed.

Example CLI syntax for the isolated clone endpoint:

```powershell
Push-Location one-stop-analytics
& 'C:\Program Files\nodejs\npx.cmd' shopify app webhook trigger `
  --api-version=2026-10 `
  --address='https://<ISOLATED_FRONTEND_HOST>/webhooks/compliance' `
  --topic=customers/data_request
Pop-Location
```

Do not substitute `https://app.smjdataai.com` for the isolated host until the payload's
test tenant identity and all referenced IDs have been independently verified.
