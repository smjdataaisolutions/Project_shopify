import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import {
  canonicalizeShopDomain,
  createTenantAssertion,
} from "../app/services/tenant-assertion.server.js";


const secret = "0123456789abcdef0123456789abcdef";

test("creates a scoped 60-second HS256 tenant assertion", () => {
  const token = createTenantAssertion({
    shop: "Fashion-Store.MyShopify.com",
    secret,
    issuer: "smj-shopify-frontend",
    audience: "smj-shopify-api",
    now: () => 1_800_000_000_000,
    assertionId: () => "assertion-1",
  });
  const [header, payload, signature] = token.split(".");
  const claims = JSON.parse(Buffer.from(payload, "base64url").toString());
  const expected = createHmac("sha256", secret)
    .update(`${header}.${payload}`)
    .digest("base64url");

  assert.equal(signature, expected);
  assert.equal(claims.sub, "fashion-store.myshopify.com");
  assert.equal(claims.shop, claims.sub);
  assert.equal(claims.iss, "smj-shopify-frontend");
  assert.equal(claims.aud, "smj-shopify-api");
  assert.equal(claims.exp - claims.iat, 60);
  assert.equal(claims.jti, "assertion-1");
});

test("rejects malformed shops and weak secrets", () => {
  assert.throws(() => canonicalizeShopDomain("https://shop.myshopify.com"));
  assert.throws(() =>
    createTenantAssertion({
      shop: "shop.myshopify.com",
      secret: "too-short",
      issuer: "frontend",
      audience: "backend",
    }),
  );
});
