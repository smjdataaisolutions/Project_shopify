# Staging deployment report

Deployment completed on 2026-10-22 for the SMJ Shopify Analytics FastAPI backend.

## Deployed resources

| Resource | Value |
| --- | --- |
| Google Cloud project | `smj-shopify-analytics` |
| Region | `us-east5` |
| Cloud Run service | `smj-shopify-api` |
| Ready revision | `smj-shopify-api-00001-xtx` |
| Traffic | 100% to the ready revision |
| Runtime service account | `smj-shopify-api-runner@smj-shopify-analytics.iam.gserviceaccount.com` |
| Artifact repository | `us-east5-docker.pkg.dev/smj-shopify-analytics/smj-shopify-api` |
| Image tag | `staging-20261022-01` |
| Image digest | `sha256:5e67262511c9bae14518e4f8b0714aa29a5493def6590de1dc5d7b009b8ef87d` |
| Database secret | `smj-shopify-neon-database-url:1` |
| Permitted invoker | `user:smjdataaisolutions@gmail.com` |

Service URL:

```text
https://smj-shopify-api-876969185947.us-east5.run.app
```

The service requires Google Cloud IAM authentication. The URL is not an anonymous
public analytics endpoint.

## Runtime settings

- Request-based billing with CPU throttling enabled.
- Minimum instances: zero (Cloud Run default; no minimum-instance annotation).
- Maximum instances: one.
- CPU: one vCPU.
- Memory: 512 MiB.
- Concurrency: eight requests per instance.
- Timeout: 60 seconds.
- Execution environment: generation 2.
- Startup CPU boost: disabled.
- FastAPI interactive documentation: disabled in staging.
- SQLAlchemy pool: two persistent plus two overflow connections at most.
- Neon connection: pooled hostname with `sslmode=require`.

## Security verification

- Anonymous `/health` request: HTTP 403.
- IAM policy contains only `user:smjdataaisolutions@gmail.com` with
  `roles/run.invoker`.
- Runtime service account has `roles/secretmanager.secretAccessor` on the database
  secret itself, not a project-wide secret accessor grant.
- The Cloud Run revision references numbered secret version `1`; no credential is
  stored in the image, YAML, source archive, or ordinary environment configuration.
- Docker runs as the unprivileged `app` user.
- The Shopify synchronization and DDL files are not present in the image.

## Validation results

- Cloud Build: successful in 32 seconds.
- Container image build and Artifact Registry push: successful.
- Authenticated `/health`: HTTP 200.
- Authenticated `/health/ready`: HTTP 200.
- Authenticated `/api/dashboard`: HTTP 200.
- Recent Cloud Run error logs after verification: none.
- Local Python suite: 206 passed, 17 skipped, zero failed.

Post-deployment Neon counts remained unchanged:

| Table | Rows |
| --- | ---: |
| `products` | 23 |
| `product_variants` | 32 |
| `locations` | 2 |
| `inventory` | 39 |
| `orders` | 13 |
| `order_line_items` | 19 |
| `shopify_sync_state` | 1 |

No database migration, DDL, synchronization, insert, update, or delete was run.

## Deployment notes

The first build attempt was stopped before Cloud Build submission because the source
archive would have included 1.9 GiB of unrelated workspace content. A `.gcloudignore`
file was added and validated; the successful build uploaded only 37 backend files,
approximately 0.26 MiB uncompressed.

The first automated authenticated check used `gcloud run services proxy`, which did not
bind its local port on this Windows environment. No cloud configuration was affected.
The verifier was updated to use a short-lived identity token and all checks then passed.

## Remaining limitation

The existing React Router frontend still makes browser-side `/api` calls and does not
send Cloud Run IAM credentials or a verified shop identity to FastAPI. It cannot call
this private staging backend directly. Do not grant `allUsers` as a workaround. A
server-side authenticated proxy belongs to the separately documented multi-tenancy and
frontend integration work.

## Cost posture

The service is configured to scale to zero and cannot scale beyond one instance. The
successful build consumed 32 Cloud Build seconds. Normal light staging traffic should
generally fit within applicable Cloud Run, Cloud Build, Artifact Registry, and Secret
Manager free allowances, but Google Cloud free usage is billing-account-wide and is not
a guarantee of a zero invoice. Cloud Run-to-Neon network egress, logs, retained images,
or usage in other projects can incur charges.

## Near-real-time synchronization release — 2026-10-23

The signed Shopify webhook bridge and seven-table FastAPI synchronization handlers
were deployed after separate approval.

| Resource | Result |
| --- | --- |
| Backend revision | `smj-shopify-api-00003-hjl` |
| Frontend revision | `smj-shopify-frontend-00007-ldk` |
| Backend image tag | `staging-20261023-realtime-01` |
| Frontend image tag | `staging-20261023-realtime-01` |
| Shopify app version | `onestop-analytics-3` |
| Backend access | IAM-private; frontend service account and approved human only |
| Frontend access | Public HTTPS for Shopify embedding |
| Scaling | Both services minimum 0, maximum 1 |

Shopify initially rejected the app version because protected customer data access had
not been selected for order webhooks. Level 1 access was selected for analytics without
requesting customer name, email, phone, or address, after which the version released
successfully. The persistent offline session was refreshed with `read_orders`,
`read_inventory`, and `read_locations` in addition to the existing scopes.

The approved one-time data-only reconciliation completed with
`SHOPIFY_APPLY_SCHEMA_DDL=false`:

| Table | Before | After |
| --- | ---: | ---: |
| `products` | 23 | 23 |
| `product_variants` | 32 | 32 |
| `inventory` | 39 | 39 |
| `locations` | 2 | 2 |
| `orders` | 13 | 14 |
| `order_line_items` | 19 | 20 |
| `shopify_sync_state` | 1 | 1 |

The newest order timestamp advanced from 2026-08-19 to 2026-10-23 and the successful
sync timestamp advanced to 2026-10-23. No schema DDL was run. Authenticated backend
health and database readiness returned HTTP 200, anonymous backend access returned
HTTP 403, and no recent Cloud Run errors were present.

During the first reconciliation attempt, an adapter mismatch caused the database
connection error to include the connection string in command output. The attempt
stopped before any database write. The utility now normalizes the SQLAlchemy URL for
psycopg and redacts configured database URLs from failures. The Neon password was
treated as compromised and rotated as recorded below.

## Neon credential rotation — 2026-10-24

The Neon password was rotated and the replacement pooled SQLAlchemy connection string
was stored as Secret Manager version `2`. Cloud Run revision
`smj-shopify-api-00004-8ml` now serves 100% of backend traffic using version `2`.

- Authenticated `/health`: HTTP 200.
- Authenticated `/health/ready`: HTTP 200, confirming Neon connectivity.
- Anonymous backend request: HTTP 403.
- Maximum instances: one; minimum instances: zero.
- Secret version `2`: enabled.
- Exposed secret version `1`: disabled (recoverable, but no longer active).

Deployment script and Cloud Run YAML defaults were updated to version `2` so future
releases do not accidentally reference the disabled credential.

### Second credential rotation — 2026-10-24

The Neon password was reset again and stored as Secret Manager version `3`. Backend
revision `smj-shopify-api-00005-szx` now serves 100% of traffic using version `3`.
Authenticated health and database readiness both returned HTTP 200; anonymous access
returned HTTP 403. Versions `1` and `2` are disabled, version `3` is enabled, and the
deployment script and YAML defaults now reference version `3`.

## Shopify session credential repair — 2026-10-24

Resetting the shared Neon role password invalidated the frontend's original session
database secret and Prisma returned `P1000`. A pooled connection to the separate
`shopify_sessions_staging` database was validated against the existing `Session` table
and stored as `smj-shopify-session-database-url` version `2`. Frontend revision
`smj-shopify-frontend-00008-6g4` now serves 100% of traffic using session secret version
`2`, with minimum zero and maximum one instance. No `P1000` errors were recorded for
the new revision during automated verification.
