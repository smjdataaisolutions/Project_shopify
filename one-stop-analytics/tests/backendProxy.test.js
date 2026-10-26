import assert from "node:assert/strict";
import test from "node:test";

import {
  getBackendProxyConfig,
  proxyAnalyticsRequest,
} from "../app/services/backend-proxy.server.js";

const shop = "test-store-martina.myshopify.com";
const config = {
  backendOrigin: "https://private-api.example.run.app",
  audience: "https://private-api.example.run.app",
  iamAuthEnabled: true,
  tenantAssertionSecret: "0123456789abcdef0123456789abcdef",
  tenantAssertionIssuer: "smj-shopify-frontend",
  tenantAssertionAudience: "smj-shopify-api",
};

function request(path = "/api/dashboard?start_date=2026-10-01", options = {}) {
  return new Request(`https://frontend.example.run.app${path}`, {
    method: options.method || "GET",
    headers: {
      Accept: options.accept || "application/json",
      Authorization: options.authorization || "Bearer shopify-id-token",
    },
  });
}

function authenticateAdminFor(authenticatedShop = shop) {
  return async () => ({ session: { shop: authenticatedShop } });
}

test("builds strict deployed proxy configuration", () => {
  const value = getBackendProxyConfig({
    DEPLOYMENT_ENVIRONMENT: "staging",
    FASTAPI_BASE_URL: "https://private-api.example.run.app",
    FASTAPI_AUDIENCE: "https://private-api.example.run.app",
    FASTAPI_IAM_AUTH_ENABLED: "true",
    TENANT_ASSERTION_SECRET: config.tenantAssertionSecret,
  });
  assert.deepEqual(value, config);
});

test("rejects disabling IAM authentication in staging", () => {
  assert.throws(() =>
    getBackendProxyConfig({
      DEPLOYMENT_ENVIRONMENT: "staging",
      FASTAPI_BASE_URL: "https://private-api.example.run.app",
      FASTAPI_IAM_AUTH_ENABLED: "false",
      TENANT_ASSERTION_SECRET: config.tenantAssertionSecret,
    }),
  );
});

test("forwards only to the configured backend with both identity layers", async () => {
  let receivedUrl;
  let receivedOptions;
  const response = await proxyAnalyticsRequest({
    request: request(),
    authenticateAdmin: authenticateAdminFor(),
    identityTokenProvider: async (audience) => {
      assert.equal(audience, config.audience);
      return "google-id-token";
    },
    tenantAssertionProvider: ({ shop: assertedShop }) => {
      assert.equal(assertedShop, shop);
      return "tenant-assertion";
    },
    fetchImplementation: async (url, options) => {
      receivedUrl = url;
      receivedOptions = options;
      return new Response(JSON.stringify({ total_orders: 13 }), {
        headers: { "Content-Type": "application/json" },
      });
    },
    config,
  });

  assert.equal(
    receivedUrl.href,
    "https://private-api.example.run.app/api/dashboard?start_date=2026-10-01",
  );
  assert.equal(
    receivedOptions.headers.get("x-tenant-assertion"),
    "tenant-assertion",
  );
  assert.equal(
    receivedOptions.headers.get("authorization"),
    "Bearer shopify-id-token",
  );
  assert.equal(
    receivedOptions.headers.get("x-serverless-authorization"),
    "Bearer google-id-token",
  );
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { total_orders: 13 });
});

test("supports another authenticated installed shop without a static allowlist", async () => {
  let assertedShop;
  const response = await proxyAnalyticsRequest({
    request: request(),
    authenticateAdmin: authenticateAdminFor("other.myshopify.com"),
    identityTokenProvider: async () => "google-id-token",
    tenantAssertionProvider: ({ shop: value }) => {
      assertedShop = value;
      return "tenant-assertion";
    },
    fetchImplementation: async () => new Response("{}"),
    config,
  });
  assert.equal(response.status, 200);
  assert.equal(assertedShop, "other.myshopify.com");
});

test("requires the Shopify ID token after admin authentication", async () => {
  const response = await proxyAnalyticsRequest({
    request: request("/api/dashboard", { authorization: "Basic invalid" }),
    authenticateAdmin: authenticateAdminFor(),
    identityTokenProvider: async () => "unused",
    tenantAssertionProvider: () => "unused",
    fetchImplementation: async () => {
      throw new Error("must not call backend");
    },
    config,
  });
  assert.equal(response.status, 401);
});

test("returns a generic gateway error when Google identity is unavailable", async () => {
  const response = await proxyAnalyticsRequest({
    request: request(),
    authenticateAdmin: authenticateAdminFor(),
    identityTokenProvider: async () => {
      throw new Error("metadata details must not reach the browser");
    },
    tenantAssertionProvider: () => "tenant-assertion",
    fetchImplementation: async () => {
      throw new Error("must not call backend");
    },
    config,
  });
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), {
    detail: "Analytics service is unavailable.",
  });
});

test("does not proxy non-analytics paths or mutating methods", async () => {
  const common = {
    authenticateAdmin: authenticateAdminFor(),
    identityTokenProvider: async () => "unused",
    tenantAssertionProvider: () => "unused",
    fetchImplementation: async () => {
      throw new Error("must not call backend");
    },
    config,
  };

  await assert.rejects(
    proxyAnalyticsRequest({ request: request("/api/health"), ...common }),
    (error) => error instanceof Response && error.status === 404,
  );
  const mutation = await proxyAnalyticsRequest({
    request: request("/api/dashboard", { method: "POST" }),
    ...common,
  });
  assert.equal(mutation.status, 405);
});

test("preserves safe CSV response headers", async () => {
  const response = await proxyAnalyticsRequest({
    request: request("/api/analytics/inventory/table/download", {
      accept: "text/csv",
    }),
    authenticateAdmin: authenticateAdminFor(),
    identityTokenProvider: async () => "google-id-token",
    tenantAssertionProvider: () => "tenant-assertion",
    fetchImplementation: async () =>
      new Response("sku,quantity\nABC,2\n", {
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition": 'attachment; filename="inventory.csv"',
          "Set-Cookie": "must-not-be-forwarded=true",
        },
      }),
    config,
  });

  assert.equal(response.headers.get("content-type"), "text/csv");
  assert.equal(
    response.headers.get("content-disposition"),
    'attachment; filename="inventory.csv"',
  );
  assert.equal(response.headers.get("set-cookie"), null);
});
