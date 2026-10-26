# SMJ Shopify frontend bridge: staging preparation

Prepared locally on 2026-10-22. This work does not deploy services, change IAM,
push Shopify configuration, or modify either Neon database.

## Security model

The browser continues to call same-origin `/api/*` URLs. React Router now owns
that route in both development and production; the former Vite-only proxy was
removed.

Shopify data changes use a separate server-only route, `/webhooks/analytics`.
React Router validates Shopify's webhook HMAC, restricts the configured shop and
topics, and forwards the unchanged signed body to the fixed IAM-private FastAPI
webhook endpoint with a Google identity token. See
`docs/realtime-shopify-sync-staging.md` for topic coverage and rollout order.

For every analytics request:

1. `authenticate.admin(request)` validates the Shopify request and loads its
   server-side session.
2. The frontend rejects any session not belonging to
   `test-store-martina.myshopify.com`.
3. The frontend forwards the short-lived Shopify ID token in `Authorization`.
   It never forwards a stored Shopify Admin API access token.
4. The frontend obtains a Google-signed identity token for the exact FastAPI
   Cloud Run audience and sends it in `X-Serverless-Authorization`.
5. Cloud Run IAM validates the frontend service account.
6. FastAPI independently verifies the Shopify token signature, audience,
   expiry, not-before time, issuer/destination relationship, and shop allowlist.

Only GET and HEAD are accepted by the proxy. Its destination origin is fixed by
`FASTAPI_BASE_URL`; the client cannot supply an upstream URL. Cookies, service
credentials, Neon credentials, Google ID tokens, and stored Shopify access
tokens are never returned to the browser.

This is a single-development-store safety boundary, not multi-tenancy. Do not
onboard an external beta merchant until the analytics schema and queries have
tenant ownership and isolation.

## Persistent Shopify sessions

The existing `prisma/dev.sqlite` remains for local development. It must not be
used on Cloud Run because container files are ephemeral.

Production uses `prisma/postgres/schema.prisma` and a separate PostgreSQL
database URL stored as `smj-shopify-session-database-url`. The included
migration creates only the Shopify `Session` table in that separate database.
Do not point this secret at the existing seven-table analytics database.

Staging currently uses session secret version `2`. Version `1` contains the old
Neon role password and should remain disabled after the version `2` frontend is
verified through Shopify Admin.

Running the session migration changes the new session database and therefore
requires separate approval:

```powershell
$gcloud = "D:\SMJ-GCloud\google-cloud-sdk\bin\gcloud.cmd"
$env:DATABASE_URL = & $gcloud secrets versions access 1 `
  --secret=smj-shopify-session-database-url `
  --project=smj-shopify-analytics
try {
  & "C:\Program Files\nodejs\npx.cmd" prisma migrate deploy `
    --schema prisma/postgres/schema.prisma
} finally {
  Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
}
```

Run that command from `one-stop-analytics` only after confirming the secret is
for the dedicated session database.

## Required Google Cloud identities and secrets

Dedicated runtime identity:

`smj-shopify-frontend-runner@smj-shopify-analytics.iam.gserviceaccount.com`

Required permissions:

- `roles/run.invoker` on `smj-shopify-api` only.
- `roles/secretmanager.secretAccessor` on
  `smj-shopify-app-api-secret` and `smj-shopify-session-database-url` only.
- The backend runtime identity also needs secret accessor on
  `smj-shopify-app-api-secret`.
- `allUsers` receives `roles/run.invoker` only on `smj-shopify-frontend`.
- Never grant `allUsers` or `allAuthenticatedUsers` on `smj-shopify-api`.

The following commands are prepared for review. They create resources and
change IAM, so do not run them without separate approval:

```powershell
$gcloud = "D:\SMJ-GCloud\google-cloud-sdk\bin\gcloud.cmd"
$project = "smj-shopify-analytics"
$region = "us-east5"
$frontendSa = "smj-shopify-frontend-runner@$project.iam.gserviceaccount.com"
$backendSa = "smj-shopify-api-runner@$project.iam.gserviceaccount.com"

& $gcloud iam service-accounts create smj-shopify-frontend-runner `
  --project=$project `
  --display-name="SMJ Shopify staging frontend"

& $gcloud secrets create smj-shopify-app-api-secret `
  --project=$project `
  --replication-policy=automatic
& $gcloud secrets create smj-shopify-session-database-url `
  --project=$project `
  --replication-policy=automatic

& $gcloud secrets add-iam-policy-binding smj-shopify-app-api-secret `
  --project=$project `
  --member="serviceAccount:$frontendSa" `
  --role=roles/secretmanager.secretAccessor
& $gcloud secrets add-iam-policy-binding smj-shopify-app-api-secret `
  --project=$project `
  --member="serviceAccount:$backendSa" `
  --role=roles/secretmanager.secretAccessor
& $gcloud secrets add-iam-policy-binding smj-shopify-session-database-url `
  --project=$project `
  --member="serviceAccount:$frontendSa" `
  --role=roles/secretmanager.secretAccessor

& $gcloud run services add-iam-policy-binding smj-shopify-api `
  --project=$project `
  --region=$region `
  --member="serviceAccount:$frontendSa" `
  --role=roles/run.invoker
```

Add secret values interactively rather than placing them on a command line or
in a repository. Version `1` means the first stored value for that named secret;
it is not part of the credential itself.

## Deployment commands (not executed)

Backend authentication must be deployed before the public frontend is tested:

```powershell
Set-Location "D:\SMJ AI Automation Solutions"
& "$PSHOME\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
  -File .\deploy\deploy-staging.ps1 `
  -ImageTag "staging-YYYYMMDD-02" `
  -Build `
  -Execute `
  -Confirm
```

Frontend preview, which performs no cloud mutations:

```powershell
Set-Location "D:\SMJ AI Automation Solutions\one-stop-analytics"
& "$PSHOME\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
  -File .\deploy\deploy-frontend-staging.ps1 `
  -ImageTag "staging-YYYYMMDD-01"
```

Approved frontend build, deployment, and narrowly scoped IAM changes:

```powershell
Set-Location "D:\SMJ AI Automation Solutions\one-stop-analytics"
& "$PSHOME\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
  -File .\deploy\deploy-frontend-staging.ps1 `
  -ImageTag "staging-YYYYMMDD-01" `
  -Build `
  -GrantBackendInvoker `
  -GrantPublicAccess `
  -Execute `
  -Confirm
```

The frontend image reuses the existing `smj-shopify-api` Artifact Registry
repository, avoiding another repository resource.

## Shopify staging configuration (not pushed)

`shopify.app.staging.toml` contains:

- Application URL:
  `https://smj-shopify-frontend-876969185947.us-east5.run.app`
- Redirect URL:
  `https://smj-shopify-frontend-876969185947.us-east5.run.app/auth/callback`

After the frontend URL responds and with separate approval, push this config:

```powershell
Set-Location "D:\SMJ AI Automation Solutions\one-stop-analytics"
& "C:\Program Files\nodejs\npx.cmd" shopify app deploy `
  --config shopify.app.staging.toml
```

Keep Shopify CLI development tunnels on the existing development configuration;
do not use staging configuration for external beta onboarding.

## Verification after an approved deployment

```powershell
Set-Location "D:\SMJ AI Automation Solutions\one-stop-analytics"
& "$PSHOME\powershell.exe" -NoProfile -ExecutionPolicy Bypass `
  -File .\deploy\verify-frontend-staging.ps1
```

Then open the app only from `test-store-martina.myshopify.com` and verify:

- Overview, Sales, Products, Orders, and Inventory load normally.
- Filters, pagination, charts, order timelines, and CSV downloads work.
- A direct anonymous backend analytics request returns 401 or 403.
- The frontend service account is the only service-account backend invoker.
- Another Shopify shop receives 403 and no analytics payload.
- Cloud Run logs contain neither authorization headers nor secret values.

## Cost controls

- Both services: minimum 0, maximum 1, request-based billing, CPU throttled.
- Frontend: 1 vCPU, 512 MiB, concurrency 8, 60-second timeout.
- Reuses the existing Artifact Registry repository.
- No VPC connector, load balancer, static IP, Cloud SQL instance, or minimum
  instance is introduced.
- Cloud Build, Artifact Registry storage, Secret Manager access/version storage,
  Cloud Run compute/requests, Neon usage, and internet egress can incur charges
  after their respective free allowances. Scale-to-zero does not guarantee a
  zero bill.
- Current Google allowances include 180,000 request-billed vCPU-seconds,
  360,000 GiB-seconds, and 2 million Cloud Run requests per billing account per
  month; 2,500 Cloud Build minutes; 0.5 GiB-month of Artifact Registry storage;
  and 6 active Secret Manager versions plus 10,000 accesses. These allowances
  are account-wide and subject to change.

## Local validation record

- Frontend Node tests: 83 passed, 0 failed.
- Frontend lint: passed.
- React Router typecheck: passed.
- Production frontend build: passed.
- Route mapping: `/api/*` resolves to `app/routes/api.$.jsx`.
- Production Prisma PostgreSQL schema validation: passed.
- Backend tests: 213 passed, 17 skipped, 0 failed.
- HTTP-level staging middleware smoke: health 200, missing token 401, wrong shop
  403. Starlette's optional `TestClient` helper was unavailable because `httpx2`
  is not installed; the same check passed directly through the ASGI middleware,
  so no test-only production dependency was added.
- Docker build: not run because Docker is not installed on this workstation.
- Cloud deployment, IAM, secret creation, session migration, Shopify config push,
  and embedded end-to-end tests: intentionally not run pending approval.
