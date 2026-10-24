import { getGoogleIdentityToken } from "./google-id-token.server.js";
import {
  canonicalizeShopDomain,
  createTenantAssertion,
} from "./tenant-assertion.server.js";

const ALLOWED_API_ROOTS = new Set([
  "analytics",
  "dashboard",
  "orders",
  "products",
  "sales",
]);

const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-disposition",
  "content-type",
  "etag",
  "last-modified",
];

function requiredEnvironmentValue(environment, name) {
  const value = environment[name]?.trim();
  if (!value) throw new Error(`${name} is required.`);
  return value;
}

function parseBoolean(value, defaultValue) {
  if (value == null || value === "") return defaultValue;
  if (value === "true") return true;
  if (value === "false") return false;
  throw new Error("FASTAPI_IAM_AUTH_ENABLED must be true or false.");
}

export function getBackendProxyConfig(environment = process.env) {
  const baseUrl = new URL(requiredEnvironmentValue(environment, "FASTAPI_BASE_URL"));
  if (baseUrl.username || baseUrl.password || baseUrl.search || baseUrl.hash) {
    throw new Error("FASTAPI_BASE_URL must not contain credentials, query, or fragment.");
  }

  const deploymentEnvironment = (
    environment.DEPLOYMENT_ENVIRONMENT || environment.NODE_ENV || "development"
  ).toLowerCase();
  const isDeployed = ["staging", "production"].includes(deploymentEnvironment);
  if (isDeployed && baseUrl.protocol !== "https:") {
    throw new Error("FASTAPI_BASE_URL must use HTTPS when deployed.");
  }

  const iamAuthEnabled = parseBoolean(
    environment.FASTAPI_IAM_AUTH_ENABLED,
    isDeployed,
  );
  if (isDeployed && !iamAuthEnabled) {
    throw new Error("FASTAPI_IAM_AUTH_ENABLED must be true when deployed.");
  }

  const audience = (environment.FASTAPI_AUDIENCE || baseUrl.origin).trim();
  if (new URL(audience).origin !== audience.replace(/\/$/, "")) {
    throw new Error("FASTAPI_AUDIENCE must be an origin without a path.");
  }

  const tenantAssertionSecret = requiredEnvironmentValue(
    environment,
    "TENANT_ASSERTION_SECRET",
  );
  if (tenantAssertionSecret.length < 32) {
    throw new Error("TENANT_ASSERTION_SECRET must contain at least 32 characters.");
  }

  return {
    backendOrigin: baseUrl.origin,
    audience: audience.replace(/\/$/, ""),
    iamAuthEnabled,
    tenantAssertionSecret,
    tenantAssertionIssuer:
      environment.TENANT_ASSERTION_ISSUER || "smj-shopify-frontend",
    tenantAssertionAudience:
      environment.TENANT_ASSERTION_AUDIENCE || "smj-shopify-api",
  };
}

function validateAnalyticsPath(requestUrl) {
  const url = new URL(requestUrl);
  if (!url.pathname.startsWith("/api/")) {
    throw new Response("Not found.", { status: 404 });
  }

  const relativePath = url.pathname.slice("/api/".length);
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(relativePath);
  } catch {
    throw new Response("Invalid API path.", { status: 400 });
  }

  if (
    !decodedPath ||
    decodedPath.includes("\\") ||
    decodedPath.includes("\0") ||
    decodedPath.split("/").some((segment) => segment === "." || segment === "..")
  ) {
    throw new Response("Invalid API path.", { status: 400 });
  }

  const root = decodedPath.split("/", 1)[0];
  if (!ALLOWED_API_ROOTS.has(root)) {
    throw new Response("Not found.", { status: 404 });
  }

  return url;
}

function bearerToken(request) {
  const authorization = request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer\s+(\S+)$/i);
  return match?.[1] || null;
}

function safeResponseHeaders(upstreamHeaders) {
  const headers = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstreamHeaders.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("x-content-type-options", "nosniff");
  headers.set("cache-control", "private, no-store");
  return headers;
}

export async function proxyAnalyticsRequest({
  request,
  authenticateAdmin,
  fetchImplementation = fetch,
  identityTokenProvider = getGoogleIdentityToken,
  tenantAssertionProvider = createTenantAssertion,
  config = getBackendProxyConfig(),
}) {
  if (typeof authenticateAdmin !== "function") {
    throw new Error("authenticateAdmin is required.");
  }
  if (!["GET", "HEAD"].includes(request.method)) {
    return new Response("Method not allowed.", {
      status: 405,
      headers: { Allow: "GET, HEAD" },
    });
  }

  const { session } = await authenticateAdmin(request);
  let authenticatedShop;
  try {
    authenticatedShop = canonicalizeShopDomain(session?.shop);
  } catch {
    return new Response("Invalid authenticated shop.", { status: 403 });
  }

  const shopifyIdToken = bearerToken(request);
  if (!shopifyIdToken) {
    return new Response("Shopify authentication is required.", { status: 401 });
  }

  const incomingUrl = validateAnalyticsPath(request.url);
  const upstreamUrl = new URL(
    `${incomingUrl.pathname}${incomingUrl.search}`,
    config.backendOrigin,
  );
  if (upstreamUrl.origin !== config.backendOrigin) {
    return new Response("Invalid API destination.", { status: 400 });
  }

  const headers = new Headers({
    Accept: request.headers.get("accept") || "application/json",
    Authorization: `Bearer ${shopifyIdToken}`,
    "X-Tenant-Assertion": tenantAssertionProvider({
      shop: authenticatedShop,
      secret: config.tenantAssertionSecret,
      issuer: config.tenantAssertionIssuer,
      audience: config.tenantAssertionAudience,
    }),
  });
  let upstreamResponse;
  try {
    if (config.iamAuthEnabled) {
      const googleIdToken = await identityTokenProvider(config.audience);
      headers.set("X-Serverless-Authorization", `Bearer ${googleIdToken}`);
    }
    upstreamResponse = await fetchImplementation(upstreamUrl, {
      method: request.method,
      headers,
      redirect: "manual",
      signal: AbortSignal.timeout(30_000),
    });
  } catch {
    return Response.json(
      { detail: "Analytics service is unavailable." },
      { status: 502 },
    );
  }

  return new Response(request.method === "HEAD" ? null : upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: safeResponseHeaders(upstreamResponse.headers),
  });
}
