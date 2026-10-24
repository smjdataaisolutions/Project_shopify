import assert from "node:assert/strict";
import test from "node:test";

import {
  forwardAnalyticsWebhook,
  getWebhookProxyConfig,
} from "../app/services/shopify-webhook-proxy.server.js";

const shop = "test-store-martina.myshopify.com";
const config = {
  backendOrigin: "https://private-api.example.run.app",
  audience: "https://private-api.example.run.app",
  tenantAssertionSecret: "0123456789abcdef0123456789abcdef",
  tenantAssertionIssuer: "smj-shopify-frontend",
  tenantAssertionAudience: "smj-shopify-api",
};

function webhookRequest(topic = "orders/create", body = '{"id":123}') {
  return new Request("https://frontend.example.run.app/webhooks/analytics", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Shopify-Hmac-Sha256": "signed-value",
      "X-Shopify-Shop-Domain": shop,
      "X-Shopify-Topic": topic,
      "X-Shopify-Webhook-Id": "webhook-1",
    },
    body,
  });
}

test("builds a fixed internal webhook destination", () => {
  assert.deepEqual(
    getWebhookProxyConfig({
      FASTAPI_BASE_URL: "https://private-api.example.run.app",
      FASTAPI_AUDIENCE: "https://private-api.example.run.app",
      TENANT_ASSERTION_SECRET: config.tenantAssertionSecret,
    }),
    config,
  );
});

test("authenticates and forwards the unchanged signed webhook using IAM", async () => {
  let forwarded;
  const request = webhookRequest();
  const response = await forwardAnalyticsWebhook({
    request,
    authenticateWebhook: async () => ({ shop }),
    identityTokenProvider: async (audience) => {
      assert.equal(audience, config.audience);
      return "google-id-token";
    },
    tenantAssertionProvider: () => "tenant-assertion",
    fetchImplementation: async (url, options) => {
      forwarded = { url, options };
      return new Response(null, { status: 204 });
    },
    config,
  });

  assert.equal(response.status, 204);
  assert.equal(
    forwarded.url.href,
    "https://private-api.example.run.app/internal/shopify-webhooks",
  );
  assert.equal(
    forwarded.options.headers.get("x-serverless-authorization"),
    "Bearer google-id-token",
  );
  assert.equal(forwarded.options.headers.get("x-shopify-topic"), "orders/create");
  assert.equal(
    forwarded.options.headers.get("x-tenant-assertion"),
    "tenant-assertion",
  );
  assert.equal(
    new TextDecoder().decode(forwarded.options.body),
    '{"id":123}',
  );
});

test("accepts another authenticated shop and rejects an unconfigured topic", async () => {
  const otherShop = await forwardAnalyticsWebhook({
    request: webhookRequest(),
    authenticateWebhook: async () => ({ shop: "other.myshopify.com" }),
    identityTokenProvider: async () => "google-id-token",
    tenantAssertionProvider: () => "tenant-assertion",
    fetchImplementation: async () => new Response(null, { status: 204 }),
    config,
  });
  assert.equal(otherShop.status, 204);

  const wrongTopic = await forwardAnalyticsWebhook({
    request: webhookRequest("customers/create"),
    authenticateWebhook: async () => ({ shop }),
    identityTokenProvider: async () => "unused",
    tenantAssertionProvider: () => "unused",
    fetchImplementation: async () => {
      throw new Error("must not forward");
    },
    config,
  });
  assert.equal(wrongTopic.status, 400);
});

test("returns a retryable failure when the private backend rejects the event", async () => {
  const response = await forwardAnalyticsWebhook({
    request: webhookRequest(),
    authenticateWebhook: async () => ({ shop }),
    identityTokenProvider: async () => "google-id-token",
    tenantAssertionProvider: () => "tenant-assertion",
    fetchImplementation: async () => new Response(null, { status: 500 }),
    config,
  });
  assert.equal(response.status, 500);
});
