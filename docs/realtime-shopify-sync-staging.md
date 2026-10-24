# Near-real-time Shopify synchronization: staging

Prepared locally on 2026-10-23. The implementation has not been deployed and the
Shopify app configuration has not been released.

## Outcome

Shopify webhooks keep all seven existing analytics tables current without schema
changes, Cloud Scheduler, or a publicly accessible FastAPI service.

| Existing table | Source events |
| --- | --- |
| `products` | product create, update, delete |
| `product_variants` | product create, update, delete |
| `inventory` | inventory item and inventory level events; location name updates |
| `locations` | location create, update, delete, activate, deactivate |
| `orders` | order create, update, delete |
| `order_line_items` | order create, update, delete |
| `shopify_sync_state` | every successfully committed webhook transaction |

This is near-real-time rather than an absolute real-time guarantee. Shopify can
retry, duplicate, delay, or occasionally deliver events out of order. The handlers
are idempotent upserts/deletes, but the current schema has no webhook-event ledger,
so periodic reconciliation remains advisable.

## Request path and trust boundaries

1. Shopify sends a signed request to the public frontend's fixed
   `/webhooks/analytics` route.
2. React Router validates it with `authenticate.webhook(request)`.
3. The frontend accepts only the configured topic and
   `test-store-martina.myshopify.com`.
4. It forwards the unchanged body and Shopify signature to the fixed private
   FastAPI `/internal/shopify-webhooks` path. It adds a short-lived Google identity
   token in `X-Serverless-Authorization` for the backend service URL audience.
5. Cloud Run IAM permits the frontend runtime service account and does not permit
   `allUsers` on the backend.
6. FastAPI independently verifies the Shopify HMAC, topic, and staging shop before
   changing data.
7. The event and `shopify_sync_state` update commit in one database transaction;
   failures roll back and return a retryable error to Shopify.

No Shopify access token, Google identity token, Neon credential, or service-account
key is exposed to the browser. The proxy cannot be directed to an arbitrary URL.

## Required Shopify configuration

The prepared Shopify TOML files request these scopes:

```text
read_inventory,read_locations,read_orders,write_products,write_metaobjects,write_metaobject_definitions
```

They subscribe `/webhooks/analytics` to:

```text
products/create, products/update, products/delete
inventory_items/create, inventory_items/update, inventory_items/delete
inventory_levels/connect, inventory_levels/update, inventory_levels/disconnect
locations/create, locations/update, locations/delete, locations/activate, locations/deactivate
orders/create, orders/update, orders/delete
```

Releasing this configuration changes requested access scopes. The development store
may require reopening or reinstalling the app to approve the new scopes. Do not
revoke the Shopify old client secret until the deployed service has moved to the new
secret and existing sessions/tokens have been migrated successfully.

## Initial catch-up

Webhooks do not replay changes that happened before subscriptions became active.
After the new release is installed and the required scopes are granted, run one
approved full reconciliation so the order created today and any other missed records
are loaded.

`job_conf/shpfy_postgre.py` now performs data-only synchronization by default.
`SHOPIFY_APPLY_SCHEMA_DDL` must remain unset (or false); setting it to true permits
the legacy DDL and is not approved for the staging analytics database.

The full-sync access token must come from a protected secret or the persistent
Shopify session store. Do not use or deploy the plaintext token currently present in
the local environment configuration. Rotate that token after a Secret Manager-based
catch-up path is prepared.

## Deployment order (requires separate approval)

1. Build and deploy the private FastAPI revision with Shopify secret version `5`.
2. Verify the backend has no public IAM member and the frontend service account is
   still its only application invoker.
3. Build and deploy the frontend revision with the webhook bridge and secret version
   `5`.
4. Release `shopify.app.staging.toml` so Shopify registers scopes and webhooks.
5. Reopen/reinstall the app if Shopify requests scope approval.
6. Run the data-only one-time reconciliation using a protected access token.
7. Create/update/delete test records in the development store and confirm the seven
   table effects and the frontend dashboards.

No new IAM role is needed: both current runtime service accounts already have access
to the Shopify API secret, and the frontend service account already has
`roles/run.invoker` on the backend.

## Verification checklist

- Anonymous calls to FastAPI return 401/403.
- Direct calls to the internal webhook endpoint cannot bypass Cloud Run IAM.
- Invalid Shopify HMAC, shop, or topic is rejected.
- Valid events return 200 only after the Neon transaction commits.
- Product changes update products and variants.
- Inventory item/level changes update inventory; location changes update locations.
- Order create/update/delete changes orders and line items.
- `shopify_sync_state.last_successful_sync_at` advances.
- Overview, Sales, Products, Orders, and Inventory continue to load through `/api/*`.
- Logs contain no authorization headers, access tokens, HMAC secrets, or database URLs.

## Known limits

- Shopify inventory-level webhooks provide the `available` state. Other inventory
  quantity states are refreshed by the full reconciliation rather than every event.
- A product webhook includes complete variant details only within Shopify's payload
  limit. For a product beyond that limit, the handler avoids unsafe deletion of
  unseen variants and reconciliation supplies the complete state.
- Without a new event-ledger column/table, strict ordering and durable webhook-ID
  deduplication cannot be added. This implementation intentionally avoids schema
  changes and relies on idempotent writes plus reconciliation.
- This remains limited to the single authorized development store and is not a
  multi-tenant design.

## Cost impact

There is no Cloud Scheduler, Cloud Run Job, VPC connector, or always-on instance.
Both services remain minimum `0`, maximum `1`, request-based. Each Shopify event can
wake the frontend and backend and access Secret Manager/Neon, so high webhook volume,
logs, image storage, builds, network egress, and Neon usage can incur charges after
free allowances. Staging traffic should normally be small, but zero cost is not
guaranteed.
