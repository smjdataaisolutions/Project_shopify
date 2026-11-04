# DEP-004: OneStop Analytics custom frontend domain

Status: the tested Worker is attached to `app.smjdataai.com`; public DNS, TLS,
React Router forwarding, and the frontend `SHOPIFY_APP_URL` update are verified.
No IAM policy, image, service account, backend setting, secret reference, production
data, or Shopify app version was changed by this work.

## Current assessment

- Intended public URL: `https://app.smjdataai.com`.
- Shopify callback: `https://app.smjdataai.com/auth/callback`.
- Public DNS resolves `app.smjdataai.com` to Cloudflare edge addresses through both
  Cloudflare (`1.1.1.1`) and Google (`8.8.8.8`) resolvers.
- Active custom-domain Worker version: `9ce6e805-1913-4a94-a6b8-ed67bfb9cd30`.
- HTTPS certificate verification passed. The observed certificate is issued by
  Google Trust Services and is valid through January 17, 2027.
- `https://app.smjdataai.com/` returned HTTP 302 to
  `https://app.smjdataai.com/app`, preserving the public hostname.
- The earlier `workers.dev` preview route was disabled when the custom-domain
  configuration was activated.
- The deployed `smj-shopify-frontend` revision is `smj-shopify-frontend-00011-grb`
  and its `SHOPIFY_APP_URL` is `https://app.smjdataai.com`.
- The previous rollback revision is `smj-shopify-frontend-00010-cvr`.
- React Router's `auth.$.jsx` catch-all calls `authenticate.admin(request)`, so
  `/auth/callback` is supported.
- The embedded app uses Shopify's `AppProvider`, persistent Prisma sessions, and
  server-side authentication. No cookie-domain override is present.
- The `/api/*` proxy still uses the private FastAPI `run.app` origin and Google ID
  tokens. DEP-004 does not replace `FASTAPI_BASE_URL` or `FASTAPI_AUDIENCE`.
- Direct Cloud Run domain mapping is unavailable in `us-east5`. Google's direct
  mapping is also Preview and is not recommended by Google for production.

## Prepared routing design

Use one Cloudflare Worker as a narrow reverse proxy:

```text
Shopify Admin/browser
        |
        v
https://app.smjdataai.com  (Cloudflare TLS and DNS)
        |
        v
Cloudflare Worker          (fixed origin allowlist)
        |
        v
smj-shopify-frontend.run.app
        |
        v
IAM-private smj-shopify-api (existing server-side Google identity token)
```

The Worker accepts only `app.smjdataai.com`, forwards the unchanged path, query,
method, headers, and body to the allowlisted frontend origin, sets forwarded-host
metadata, and rewrites any Cloud Run absolute redirect to the public hostname. It
contains no Shopify, Google, or Neon credential. The apex `smjdataai.com` hostname
is not configured, so the existing website is unaffected.

Cloudflare Worker Custom Domains create the DNS record and edge certificate. The
Workers Free plan currently permits 100,000 requests per day, but limits and pricing
must be rechecked before activation. If availability requirements outgrow this
bridge, use Google's recommended global external Application Load Balancer after a
separate cost review.

## Local configuration changes

- Both Shopify TOML files use `https://app.smjdataai.com` and the matching callback.
- Frontend deployment defaults set `SHOPIFY_APP_URL=https://app.smjdataai.com`.
- The private FastAPI URL and audience are unchanged.
- The verification script defaults to the custom domain but accepts the old URL as
  a rollback/test parameter.
- Cloudflare preview and production Worker configurations are under
  `one-stop-analytics/cloudflare/custom-domain-worker`.

## PowerShell activation procedure

Run only after Cloudflare resource creation and production traffic changes are
explicitly approved.

```powershell
Set-Location 'D:\SMJ AI Automation Solutions\Project_shopify\one-stop-analytics'

# Authenticate to the Cloudflare account that owns smjdataai.com.
npx.cmd wrangler@latest login

# Stage 1: deploy the same Worker on its workers.dev preview URL only. (Completed.)
npx.cmd wrangler@latest deploy --config '.\cloudflare\custom-domain-worker\wrangler.preview.jsonc'

# Copy the workers.dev URL printed by Wrangler, then verify it reaches the frontend.
curl.exe -I 'https://WORKER-NAME.ACCOUNT-SUBDOMAIN.workers.dev/'

# Stage 2: after preview approval, attach app.smjdataai.com. (Completed.)
# This creates/changes Cloudflare DNS and TLS and therefore changes production traffic.
npx.cmd wrangler@latest deploy --config '.\cloudflare\custom-domain-worker\wrangler.jsonc'

Resolve-DnsName 'app.smjdataai.com'
curl.exe -I 'https://app.smjdataai.com/'
```

After HTTPS routing is verified, update the existing Cloud Run frontend environment
without changing the backend, IAM, secrets, scaling, or image. (Completed.)

```powershell
$Gcloud = (Get-Command 'gcloud.cmd').Source
$PreviousRevision = (& $Gcloud run services describe 'smj-shopify-frontend' `
  --project 'smj-shopify-analytics' `
  --region 'us-east5' `
  --format='value(status.latestReadyRevisionName)').Trim()

& $Gcloud run services update 'smj-shopify-frontend' `
  --project 'smj-shopify-analytics' `
  --region 'us-east5' `
  --update-env-vars 'SHOPIFY_APP_URL=https://app.smjdataai.com' `
  --min-instances 0 `
  --max-instances 1

Write-Host "Rollback revision: $PreviousRevision"
```

Do not change `FASTAPI_BASE_URL`, `FASTAPI_AUDIENCE`, secret bindings, runtime
service account, or backend IAM. Do not release the Shopify configuration until
the domain and frontend revision both work.

The Shopify release remains a separate approved action:

```powershell
Set-Location 'D:\SMJ AI Automation Solutions\Project_shopify\one-stop-analytics'
shopify.cmd app config use 'shopify.app.staging.toml'
shopify.cmd app deploy
```

Review the generated version diff before confirming a release. The configuration
includes custom URLs, compliance webhooks, and least-privilege scopes.

## Verification after authorized activation

1. Confirm DNS resolves and HTTPS has a valid certificate.
2. Confirm `/` and `/auth/callback` reach React Router without a host error.
3. Open the app from each authorized Shopify store and test install/reinstall.
4. Confirm Overview, Sales, Inventory, Orders, and Products load.
5. Confirm browser traffic uses only `app.smjdataai.com`; no Google ID token,
   Shopify token, or database credential is exposed.
6. Confirm `/api/*` calls succeed and direct anonymous FastAPI calls remain 401/403.
7. Confirm tenant isolation and automatic synchronization for both stores.
8. Trigger valid compliance test webhooks and an invalid-HMAC request after the
   compliance build is separately deployed.

## Rollback

Keep the old Cloud Run URL enabled during the initial stability period.

```powershell
$Gcloud = (Get-Command 'gcloud.cmd').Source

# Restore the previous known-good frontend revision captured during activation.
& $Gcloud run services update-traffic 'smj-shopify-frontend' `
  --project 'smj-shopify-analytics' `
  --region 'us-east5' `
  --to-revisions "${PreviousRevision}=100"
```

Then restore the Shopify App URL and callback to the old frontend URL in a reviewed
Shopify app version. Removing the Cloudflare Worker Custom Domain or Worker changes
DNS/TLS and is destructive; perform it only with explicit approval after Shopify is
restored. The existing root website must not be modified during rollback.

## Remaining blockers

- Cloudflare account/zone access and plan limits have not been verified.
- The custom domain is attached and DNS/HTTPS routing is verified.
- Cloud Run uses the custom `SHOPIFY_APP_URL`; root routing and the authentication
  endpoints reach React Router. Direct incomplete authentication probes return 410
  from Shopify's application authentication layer, as they lack the required
  embedded `host`/session token or OAuth code/HMAC.
- The Shopify version state (draft versus released) must be confirmed before any
  release action.
- Embedded authentication and all five modules require live verification after the
  Shopify version using the custom URL is active and the app is opened from Shopify
  Admin.
