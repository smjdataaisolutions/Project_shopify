# MT-001 local implementation report

Status: locally implemented and tested; not migrated or deployed.

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

## New cloud prerequisite (do not execute without approval)

Both existing runtime identities need Secret Manager accessor on one dedicated secret:

- `smj-shopify-frontend-runner@smj-shopify-analytics.iam.gserviceaccount.com`
- `smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com`

PowerShell preparation commands:

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
$secretValue | & $gcloud secrets versions add $secretName `
  --project $project `
  --data-file=-
$secretValue = $null
$randomBytes = $null

& $gcloud secrets add-iam-policy-binding $secretName `
  --project $project `
  --member 'serviceAccount:smj-shopify-frontend-runner@smj-shopify-analytics.iam.gserviceaccount.com' `
  --role 'roles/secretmanager.secretAccessor'

& $gcloud secrets add-iam-policy-binding $secretName `
  --project $project `
  --member 'serviceAccount:smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com' `
  --role 'roles/secretmanager.secretAccessor'
```

These commands create/modify cloud resources and IAM and were not run.

## Prepared deployment commands (do not execute yet)

After backup, Neon-branch rehearsal, live migration approval, secret creation, image
build approval and coordinated downtime approval:

```powershell
& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' `
  -NoProfile -ExecutionPolicy Bypass `
  -File '.\deploy\deploy-staging.ps1' `
  -ImageTag '<BACKEND_IMAGE_TAG>' -Build -Execute -Confirm

& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' `
  -NoProfile -ExecutionPolicy Bypass `
  -File '.\one-stop-analytics\deploy\deploy-frontend-staging.ps1' `
  -ImageTag '<FRONTEND_IMAGE_TAG>' -Build -Execute -Confirm
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

1. Verify a recoverable Neon backup.
2. Rehearse against a Neon branch using the current live 23/32/2/39/15/21/1 baseline.
3. Create and permission the assertion secret.
4. Obtain explicit approval for live migration and deployment.
5. Verify the development store, then a second authorized test store.
6. Complete Milestone 3 before promising automatic initial sync to beta merchants.

Known issue: two preserved inventory rows reference deleted locations. The FK is
enforced for new rows but remains `NOT VALID` until those historical records are resolved.

Repository layout: the deployed application code and MT-001 changes have been
consolidated into `D:\SMJ AI Automation Solutions\Project_shopify` on the
`feature/mt-001-multi-tenant` branch. The older `GIT` checkout and standalone source
folders are retained only as local backups and are no longer the authoritative Git
worktree.
