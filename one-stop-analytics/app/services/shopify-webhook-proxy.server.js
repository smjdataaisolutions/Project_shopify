import { getGoogleIdentityToken } from "./google-id-token.server.js";
import {
  canonicalizeShopDomain,
  createTenantAssertion,
} from "./tenant-assertion.server.js";

const ALLOWED_TOPICS = new Set([
  "app/uninstalled",
  "inventory_items/create",
  "inventory_items/delete",
  "inventory_items/update",
  "inventory_levels/connect",
  "inventory_levels/disconnect",
  "inventory_levels/update",
  "locations/activate",
  "locations/create",
  "locations/deactivate",
  "locations/delete",
  "locations/update",
  "orders/create",
  "orders/delete",
  "orders/updated",
  "products/create",
  "products/delete",
  "products/update",
]);

function requiredEnvironmentValue(environment, name) {
  const value = environment[name]?.trim();
  if (!value) throw new Error(`${name} is required.`);
  return value;
}

export function getWebhookProxyConfig(environment = process.env) {
  const backendOrigin = new URL(
    requiredEnvironmentValue(environment, "FASTAPI_BASE_URL"),
  ).origin;
  const audience = (
    environment.FASTAPI_AUDIENCE || backendOrigin
  ).trim().replace(/\/$/, "");
  const tenantAssertionSecret = requiredEnvironmentValue(
    environment,
    "TENANT_ASSERTION_SECRET",
  );
  if (tenantAssertionSecret.length < 32) {
    throw new Error("TENANT_ASSERTION_SECRET must contain at least 32 characters.");
  }
  return {
    backendOrigin,
    audience,
    tenantAssertionSecret,
    tenantAssertionIssuer:
      environment.TENANT_ASSERTION_ISSUER || "smj-shopify-frontend",
    tenantAssertionAudience:
      environment.TENANT_ASSERTION_AUDIENCE || "smj-shopify-api",
  };
}

export async function forwardAnalyticsWebhook({
  request,
  authenticateWebhook,
  fetchImplementation = fetch,
  identityTokenProvider = getGoogleIdentityToken,
  tenantAssertionProvider = createTenantAssertion,
  config = getWebhookProxyConfig(),
}) {
  const rawBody = await request.clone().arrayBuffer();
  const { shop } = await authenticateWebhook(request);
  let normalizedShop;
  try {
    normalizedShop = canonicalizeShopDomain(shop);
  } catch {
    return new Response("Invalid authenticated shop.", { status: 403 });
  }

  const topic = request.headers.get("x-shopify-topic")?.toLowerCase() || "";
  const hmac = request.headers.get("x-shopify-hmac-sha256") || "";
  if (!ALLOWED_TOPICS.has(topic) || !hmac) {
    return new Response("Unsupported Shopify webhook.", { status: 400 });
  }

  const googleIdToken = await identityTokenProvider(config.audience);
  const headers = new Headers({
    "Content-Type": "application/json",
    "X-Serverless-Authorization": `Bearer ${googleIdToken}`,
    "X-Shopify-Hmac-Sha256": hmac,
    "X-Shopify-Shop-Domain": normalizedShop,
    "X-Shopify-Topic": topic,
    "X-Tenant-Assertion": tenantAssertionProvider({
      shop: normalizedShop,
      secret: config.tenantAssertionSecret,
      issuer: config.tenantAssertionIssuer,
      audience: config.tenantAssertionAudience,
    }),
  });
  for (const name of ["x-shopify-webhook-id", "x-shopify-triggered-at"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  let response;
  try {
    response = await fetchImplementation(
      new URL("/internal/shopify-webhooks", config.backendOrigin),
      {
        method: "POST",
        headers,
        body: rawBody,
        redirect: "manual",
        signal: AbortSignal.timeout(30_000),
      },
    );
  } catch {
    return new Response("Webhook synchronization is unavailable.", {
      status: 503,
    });
  }

  if (!response.ok) {
    console.error(`Analytics webhook forwarding failed with ${response.status}.`);
    return new Response("Webhook synchronization failed.", { status: 500 });
  }
  return new Response(null, { status: 204 });
}
