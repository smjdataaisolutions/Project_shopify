# SMJ FastAPI staging deployment

This document prepares the FastAPI analytics backend for an IAM-protected Cloud Run
staging service. It does not deploy the React Router application and does not run the
Shopify full-synchronization script or database DDL. The separately prepared,
event-driven synchronization path is documented in
`docs/realtime-shopify-sync-staging.md`.

## Fixed staging configuration

| Setting | Value |
| --- | --- |
| Project | `smj-shopify-analytics` |
| Region | `us-east5` (Columbus) |
| Service | `smj-shopify-api` |
| Runtime service account | `smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com` |
| Permitted human invoker | `smjdataaisolutions@gmail.com` |
| Artifact Registry repository | `smj-shopify-api` |
| Database secret | `smj-shopify-neon-database-url` |
| Minimum/maximum instances | `0` / `1` |
| CPU and memory | `1` vCPU / `512Mi` |
| Concurrency | `8` |
| Billing | Request-based (CPU throttled outside requests) |
| Public access | Disabled; Cloud Run IAM authentication required |

`us-east5` is geographically close to the Neon AWS US East 2 (Ohio) database. The
service talks to Neon over its public TLS endpoint; no VPC connector or Cloud SQL
connector is required.

## Database secret format

Use the pooled Neon connection string and change the SQLAlchemy driver prefix to
`postgresql+psycopg`. TLS must be required:

```text
postgresql+psycopg://USER:PASSWORD@POOLER_HOST/DATABASE?sslmode=require
```

Store this complete value as a numbered version of
`smj-shopify-neon-database-url`. Staging currently uses version `3`; versions `1` and
`2` are disabled after credential rotations on 2026-10-24. Do not put the value in
YAML, source control, command history, build arguments, or ordinary environment files.
Enter the value in the Google Cloud Secret Manager console when possible.

Cloud Run resolves the numbered secret version into `DATABASE_URL` when an instance
starts. The dedicated runtime service account should receive
`roles/secretmanager.secretAccessor` on this secret only, not at project level.

## Local validation

From PowerShell in the backend root:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
& .\.venv\Scripts\python.exe -m compileall -q app tests
& .\.venv\Scripts\python.exe -m scripts.validate_database_readonly
```

If Docker is installed:

```powershell
docker build --pull --tag smj-shopify-api:staging-local .
docker run --rm --name smj-shopify-api-local `
  --env-file .env `
  --publish 8080:8080 `
  smj-shopify-api:staging-local
```

In another PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/health/ready
```

The local `.env` must never be added to an image or committed. The `.dockerignore`
explicitly excludes it, the frontend, DDL, synchronization code, tests, archives, and
local repositories. The matching `.gcloudignore` keeps those files out of the Cloud
Build source upload as well.

## Cloud prerequisites — do not run without approval

The following commands enable APIs and create or change cloud resources. They are
provided for a separately approved deployment session and were not run during local
preparation.

```powershell
$ProjectId = "smj-shopify-analytics"
$Region = "us-east5"
$Repository = "smj-shopify-api"
$ServiceAccountId = "smj-shopify-api-runner"
$ServiceAccount = "$ServiceAccountId@$ProjectId.iam.gserviceaccount.com"
$SecretName = "smj-shopify-neon-database-url"

gcloud services enable `
  run.googleapis.com `
  artifactregistry.googleapis.com `
  cloudbuild.googleapis.com `
  secretmanager.googleapis.com `
  iam.googleapis.com `
  --project=$ProjectId

gcloud artifacts repositories create $Repository `
  --project=$ProjectId `
  --location=$Region `
  --repository-format=docker `
  --description="SMJ Shopify API staging images"

gcloud iam service-accounts create $ServiceAccountId `
  --project=$ProjectId `
  --display-name="SMJ Shopify API Cloud Run staging"

gcloud secrets create $SecretName `
  --project=$ProjectId `
  --replication-policy=automatic

gcloud secrets add-iam-policy-binding $SecretName `
  --project=$ProjectId `
  --member="serviceAccount:$ServiceAccount" `
  --role="roles/secretmanager.secretAccessor"
```

Add secret version `1` through the Secret Manager console so the connection string is
not exposed in PowerShell history. Confirm that the value uses the pooled Neon host,
the `postgresql+psycopg` prefix, and `sslmode=require`.

The deploying identity also needs the minimum roles required to submit builds, deploy
Cloud Run, and act as the runtime service account. Do not assign owner/editor roles for
this purpose.

## Deployment commands — do not run without approval

Preview the prepared deployment script; this performs no cloud calls:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\deploy\deploy-staging.ps1 `
  -ImageTag "staging-YYYYMMDD-HHMM"
```

After explicit build/deployment/IAM approval:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\deploy\deploy-staging.ps1 `
  -ImageTag "staging-YYYYMMDD-HHMM" `
  -Build `
  -GrantInvoker `
  -Execute `
  -Confirm
```

The script uses Cloud Build, deploys with `--no-allow-unauthenticated`, binds the
numbered database secret, caps scaling at one instance, and grants Cloud Run Invoker
only when `-GrantInvoker` is supplied. The declarative target state is also recorded in
`deploy/cloudrun-staging.template.yaml`; replace `IMAGE_TAG` before applying it.

## Post-deployment verification

Run only after deployment and IAM approval:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\deploy\verify-staging.ps1
```

The verifier checks that an anonymous request is rejected, obtains a short-lived Google
identity token, and checks `/health`, `/health/ready`, and `/api/dashboard`. It reports
status only and does not print the token or analytics data.

Also review the revision configuration:

```powershell
gcloud run services describe smj-shopify-api `
  --project=smj-shopify-analytics `
  --region=us-east5 `
  --format=export

gcloud run services get-iam-policy smj-shopify-api `
  --project=smj-shopify-analytics `
  --region=us-east5
```

There must be no `allUsers` or `allAuthenticatedUsers` member. Compare the seven Neon
table counts before and after the smoke test using read-only queries; deployment itself
does not run migrations, DDL, sync jobs, inserts, updates, or deletes.

## Frontend limitation

The existing React code makes browser-side relative `/api` calls and only Vite's local
development server proxies them to FastAPI. Shopify page authentication is not sent to
FastAPI. Consequently, an IAM-private Cloud Run service can be tested by approved
operators but cannot yet be called directly by the existing browser application.

Resolving that requires a separately approved frontend/server integration, such as an
authenticated React Router server proxy that invokes Cloud Run using its service
identity and forwards a verified Shopify shop context. Publishing FastAPI to work
around this limitation would expose merchant analytics and is not acceptable.

## Rollback

Cloud Run retains revisions. To send traffic to a known prior revision:

```powershell
gcloud run services update-traffic smj-shopify-api `
  --project=smj-shopify-analytics `
  --region=us-east5 `
  --to-revisions="REVISION_NAME=100"
```

Rollback changes only Cloud Run traffic. It does not touch Neon data because the API
container performs no schema or data mutations.

## Cost controls

- Minimum instances `0` and request-based billing avoid idle compute charges.
- Maximum instances `1` prevents an unexpected scale-out bill and bounds database
  connections to four (`pool_size=2`, `max_overflow=2`).
- One vCPU, `512Mi`, concurrency `8`, and CPU throttling keep the staging footprint
  small.
- One numbered Secret Manager version stays within its small free allowance under
  normal staging use.
- Container images consume Artifact Registry storage until old images are removed.
- Cloud Build and outbound Cloud Run-to-Neon traffic can incur charges. Set a small
  project budget and billing alert; budgets alert but do not hard-stop spending.
- Google Cloud free-tier quotas are billing-account-wide and are not a guarantee of a
  zero invoice. Taxes, network egress, logging volume, and usage in other projects can
  still produce charges.

At the time this plan was prepared, Google's published monthly request-based Cloud Run
free tier was 180,000 vCPU-seconds, 360,000 GiB-seconds, and 2 million requests. The
published allowances also included 2,500 Cloud Build minutes, 0.5 GiB-month of Artifact
Registry storage, and six active Secret Manager versions plus 10,000 secret access
operations. These allowances are shared at billing-account level and can change.
Cloud Run outbound traffic to Neon is internet egress; Google currently lists 1 GiB of
free North America outbound transfer per month before network charges. A lightly used
staging service with one small image is likely to remain near $0, but no fixed zero-cost
guarantee is possible.

## Synchronization process

`job_conf/shpfy_postgre.py` is a standalone full synchronization program. It reads
`SHOPIFY_STORE`, `SHOPIFY_ACCESS_TOKEN`, `SHOPIFY_API_VERSION`, and `DATABASE_URL` and
upserts Shopify data. Schema DDL is now disabled by default and is allowed only when
`SHOPIFY_APPLY_SCHEMA_DDL=true`; that flag must not be used against staging. The script
remains excluded from the API image and is not scheduled by this deployment.

Near-real-time updates are prepared through signed Shopify webhooks routed through
the authenticated frontend bridge to the IAM-private backend. Webhooks cover all seven
existing analytics tables without schema changes. A data-only full reconciliation is
still required after first release because Shopify does not replay older changes.
