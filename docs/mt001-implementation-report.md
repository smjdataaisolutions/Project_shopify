# MT-001 local implementation report

Status: implemented, production-migrated and deployed to staging on 26 October 2026.

## Delivered

- Shared-database tenant model and guarded migration/rollback.
- Automatic tenant registration from verified Shopify identity.
- Shopify token plus 60-second server-signed tenant assertion.
- Fail-closed tenant SQLAlchemy session for every merchant analytics route.
- Tenant-scoped webhooks, deletes, upserts, joins, exports, sync state and full-sync
  foundation.
- Uninstall lifecycle marking without deleting analytics history.
- Two-tenant PostgreSQL isolation tests and existing five-module regression coverage.
- Cloud Run configuration prepared for one additional shared Secret Manager secret.

The Prisma `Session` schema remains unchanged and already supports multiple shops using
its indexed `shop` field. Access tokens remain only in that separate session database.

## Test results

- Backend baseline before changes: 221 passed, 17 skipped.
- Backend after changes: 232 passed, 23 skipped (integration suite opt-in).
- Tenant PostgreSQL integration: 6 passed using two synthetic shops and reused IDs.
- Tenant API middleware: 2 passed.
- Frontend: 89 passed.
- React Router production build: passed.
- Migration: passed on disposable local `shopify_ai_mt001_test`.
- PowerShell deployment previews: passed; no cloud commands executed.
- Cloud Run YAML parsing: passed.

Expected test logs include deliberately raised SQLAlchemy errors from error-mapping unit
tests and one simulated webhook-forwarding 500. They do not indicate suite failures.

## Cloud secret configuration

Both existing runtime identities need Secret Manager accessor on one dedicated secret:

- `smj-shopify-frontend-runner@smj-shopify-analytics.iam.gserviceaccount.com`
- `smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com`

Reference PowerShell preparation commands (do not rerun without approval):

```powershell
$gcloud = 'C:\Users\Shem Dennis\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$project = 'smj-shopify-analytics'
$secretName = 'smj-shopify-tenant-assertion-secret'

& $gcloud secrets create $secretName `
  --project $project `
  --replication-policy automatic

$randomBytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($randomBytes)
$rng.Dispose()
$secretValue = [Convert]::ToBase64String($randomBytes)
$secretFile = Join-Path ([IO.Path]::GetTempPath()) `
  ("smj-tenant-secret-{0}.txt" -f [guid]::NewGuid().ToString('N'))
try {
  [IO.File]::WriteAllText(
    $secretFile,
    $secretValue,
    [Text.UTF8Encoding]::new($false)
  )
  & $gcloud secrets versions add $secretName `
    --project $project `
    --data-file=$secretFile
}
finally {
  Remove-Item -LiteralPath $secretFile -Force -ErrorAction SilentlyContinue
  $secretValue = $null
  $randomBytes = $null
}

& $gcloud secrets add-iam-policy-binding $secretName `
  --project $project `
  --member 'serviceAccount:smj-shopify-frontend-runner@smj-shopify-analytics.iam.gserviceaccount.com' `
  --role 'roles/secretmanager.secretAccessor'

& $gcloud secrets add-iam-policy-binding $secretName `
  --project $project `
  --member 'serviceAccount:smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com' `
  --role 'roles/secretmanager.secretAccessor'
```

These commands create/modify cloud resources and IAM. The staging prerequisite was
completed under explicit approval; this example is retained for controlled recovery or
future environment setup.

## Deployment commands

Use these only after explicit deployment approval. Omitting the IAM grant switches
preserves the existing Cloud Run IAM policies:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' `
  -NoProfile -ExecutionPolicy Bypass `
  -File '.\deploy\deploy-staging.ps1' `
  -ImageTag '<BACKEND_IMAGE_TAG>' -Execute -Confirm

& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' `
  -NoProfile -ExecutionPolicy Bypass `
  -File '.\one-stop-analytics\deploy\deploy-frontend-staging.ps1' `
  -ImageTag '<FRONTEND_IMAGE_TAG>' -Execute -Confirm
```

Do not use `-GrantInvoker` or `-GrantBackendInvoker` unless an IAM check shows the
existing scoped bindings are missing. Never grant `allUsers` to FastAPI.

## Cost considerations

No new always-on compute is introduced. Both services remain request-based with minimum
0 and maximum 1 instance. One small Secret Manager secret/version adds negligible usage
but is billable outside free allowances. A Neon branch may consume branch storage and
compute while active. Cloud Build and Artifact Registry can incur build-minute and image
storage charges; remove obsolete images only under a separate cleanup approval.

## Remaining release gates

1. Verify a second authorized development store against the deployed services.
2. Continue monitoring tenant authorization and synchronization logs before beta onboarding.
3. Complete Milestone 3 before promising automatic initial sync to beta merchants.

Completed on 26 October 2026: manual Neon snapshot
`pre-mt001-2026-10-26 04:21:11 UTC (manual)` and disposable branch rehearsal on
`mt001-rehearsal-2026-10-26` (`neondb`). Counts remained 23/32/2/39/15/21/1 and 15
read-only database regression tests passed across all five modules.

Completed on 26 October 2026: Secret Manager secret
`smj-shopify-tenant-assertion-secret`. Version 1 was found to contain a trailing newline;
normalized version 2 is now active on both services. Version 1 remains enabled
temporarily but must not be selected. The only secret-level IAM members are the frontend
and backend runtime service accounts, each with `roles/secretmanager.secretAccessor`.

Completed on 26 October 2026: migration `001_multi_tenant` applied to production
database `neondb` using snapshot `pre-mt001-2026-10-26 04:21:11 UTC (manual)` as the
recovery reference. Backend revision `smj-shopify-api-00007-rz2` and frontend revision
`smj-shopify-frontend-00010-cvr` serve 100% traffic with image tag
`mt001-20261026-02`. Both services remain request-based at minimum 0 and maximum 1.
Backend IAM remains private and both IAM policies were unchanged. The authenticated
development-store bridge and tenant-scoped analytics request returned HTTP 200.

Known accepted issue: two preserved inventory rows reference deleted location
`Snow City Warehouse`. They cannot be safely mapped to either active location. The FK is
enforced for new rows but remains `NOT VALID` for those historical records.

Repository layout: the deployed application code and MT-001 changes are consolidated
in `D:\SMJ AI Automation Solutions\Project_shopify` on the `main` branch. The obsolete
`GIT` checkout was removed and the
former standalone sources were moved to the dated `Archive` backup.
