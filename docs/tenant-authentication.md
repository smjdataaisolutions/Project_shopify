# Tenant authentication and authorization

Cloud Run IAM proves the frontend service identity, not the merchant. MT-001 uses:

- Google ID token in `X-Serverless-Authorization` for Cloud Run IAM.
- Shopify ID token in `Authorization`, verified by FastAPI for signature, audience,
  issuer/destination equality and expiry.
- Server-generated tenant assertion in `X-Tenant-Assertion`, signed with a dedicated
  secret and valid for 60 seconds.

The assertion requires `iss`, `aud`, `sub`, `shop`, `iat`, `nbf`, `exp`, and `jti`.
`sub` and `shop` must match a canonical `.myshopify.com` domain. FastAPI also requires
that shop to match the independently verified Shopify token.

Store the 32+ character random secret in Secret Manager as
`smj-shopify-tenant-assertion-secret`. Only the frontend and backend runtime service
accounts should read it. Never expose it in browser code, logs, Git, Shopify config, or
analytics tables.

Staging currently uses secret version `2`. Version `1` contains a trailing newline from
its original PowerShell pipeline creation and must not be selected for either service.
Both services must reference the same normalized secret version. Create future versions
from a binary-safe temporary file without a BOM or trailing newline.

Missing, malformed, forged or expired assertions return 401. A valid assertion whose
shop differs from the Shopify token returns 403. Request parameters and plain shop
headers never authorize a tenant.
