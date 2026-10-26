# Multi-tenant architecture

## Request path

1. Shopify App Bridge sends a Shopify ID token to React Router `/api/*`.
2. React Router calls `authenticate.admin(request)` and derives the verified shop.
3. The server signs a 60-second tenant assertion with issuer, audience, shop subject,
   timestamps and a unique assertion ID.
4. It obtains a Google identity token for the fixed private FastAPI origin.
5. Cloud Run IAM authenticates the service account. FastAPI independently verifies the
   Shopify token and tenant assertion and requires both shop identities to match.
6. FastAPI idempotently registers/reactivates the shop, resolves `shops.id`, and opens a
   tenant-scoped SQLAlchemy session.
7. SQLAlchemy applies `shop_id` to every ORM read. Merchant sessions reject raw SQL.

Browser input never selects `shop_id`. Shopify access tokens, Google tokens, signing
secrets and Neon credentials remain server-side.

## Data model

`shops.shop_domain` is canonical and unique; internal `BIGINT shops.id` owns rows.
Access tokens remain in the separate Prisma `Session` database.

- `products`: `(shop_id, id)`
- `product_variants`: `(shop_id, id)` plus composite product FK
- `locations`: `(shop_id, id)`
- `inventory`: `(shop_id, inventory_item_id, location_id)`
- `orders`: `(shop_id, id)`
- `order_line_items`: `(shop_id, id)` plus composite order FK
- `shopify_sync_state`: `(shop_id, source)`

Tenant-first indexes support filters and joins. Webhook and reconciliation raw SQL
includes `shop_id` in reads, writes, conflict targets and deletes.

## Installation and lifecycle

The first authenticated analytics request registers a shop with pending sync. Repeated
registration is idempotent and reinstall reactivates the same tenant. New tenants see
empty analytics—never development-store fallback data. `app/uninstalled` deletes that
shop's sessions and marks only its analytics tenant uninstalled without deleting history.

No shared analytics cache was found. Proxy responses use `private, no-store`; exports
use tenant-scoped repositories. RLS remains a pooling-aware defense-in-depth follow-up.
