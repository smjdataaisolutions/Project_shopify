import { createHmac, randomUUID } from "node:crypto";

const SHOP_DOMAIN_PATTERN =
  /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.myshopify\.com$/;

export function canonicalizeShopDomain(value) {
  const shop = String(value || "").trim().toLowerCase().replace(/\.$/, "");
  if (!SHOP_DOMAIN_PATTERN.test(shop)) {
    throw new Error("Invalid Shopify shop domain.");
  }
  return shop;
}

function encode(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

export function createTenantAssertion({
  shop,
  secret,
  issuer,
  audience,
  now = () => Date.now(),
  assertionId = () => randomUUID(),
}) {
  if (!secret || secret.length < 32) {
    throw new Error("TENANT_ASSERTION_SECRET must contain at least 32 characters.");
  }
  const canonicalShop = canonicalizeShopDomain(shop);
  const issuedAt = Math.floor(now() / 1000);
  const header = encode({ alg: "HS256", typ: "JWT" });
  const payload = encode({
    iss: issuer,
    aud: audience,
    sub: canonicalShop,
    shop: canonicalShop,
    iat: issuedAt,
    nbf: issuedAt - 1,
    exp: issuedAt + 60,
    jti: assertionId(),
  });
  const unsigned = `${header}.${payload}`;
  const signature = createHmac("sha256", secret)
    .update(unsigned)
    .digest("base64url");
  return `${unsigned}.${signature}`;
}
