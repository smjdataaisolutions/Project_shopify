const PUBLIC_HOSTNAME = "app.smjdataai.com";
const PREVIEW_HOSTNAME =
  "smj-shopify-frontend-domain-proxy.smjdataaisolutions.workers.dev";
const ALLOWED_PUBLIC_HOSTNAMES = new Set([PUBLIC_HOSTNAME, PREVIEW_HOSTNAME]);
const DEFAULT_ORIGIN =
  "https://smj-shopify-frontend-876969185947.us-east5.run.app";
const ALLOWED_ORIGINS = new Set([
  DEFAULT_ORIGIN,
  "https://smj-shopify-frontend-3douxa5qja-ul.a.run.app",
]);

function configuredOrigin(environment = {}) {
  const value = (environment.CLOUD_RUN_ORIGIN || DEFAULT_ORIGIN).replace(/\/$/, "");
  if (!ALLOWED_ORIGINS.has(value)) {
    throw new Error("CLOUD_RUN_ORIGIN is not an approved frontend origin.");
  }
  return new URL(value);
}

function configuredPublicHostname(environment = {}) {
  const value = environment.PUBLIC_HOSTNAME || PUBLIC_HOSTNAME;
  if (!ALLOWED_PUBLIC_HOSTNAMES.has(value)) {
    throw new Error("PUBLIC_HOSTNAME is not approved.");
  }
  return value;
}

export async function proxyCustomDomainRequest(
  request,
  environment = {},
  fetchImplementation = fetch,
) {
  const publicUrl = new URL(request.url);
  const publicHostname = configuredPublicHostname(environment);
  if (publicUrl.protocol !== "https:" || publicUrl.hostname !== publicHostname) {
    return new Response("Misdirected request.", { status: 421 });
  }

  const origin = configuredOrigin(environment);
  const originUrl = new URL(publicUrl.pathname + publicUrl.search, origin);
  const originRequest = new Request(originUrl, request);
  originRequest.headers.set("X-Forwarded-Host", publicUrl.host);
  originRequest.headers.set("X-Forwarded-Proto", "https");

  const originResponse = await fetchImplementation(originRequest, {
    redirect: "manual",
  });
  const responseHeaders = new Headers(originResponse.headers);
  const location = responseHeaders.get("location");
  if (location) {
    const locationUrl = new URL(location, origin);
    if (ALLOWED_ORIGINS.has(locationUrl.origin)) {
      locationUrl.protocol = "https:";
      locationUrl.host = publicHostname;
      responseHeaders.set("location", locationUrl.toString());
    }
  }

  return new Response(originResponse.body, {
    status: originResponse.status,
    statusText: originResponse.statusText,
    headers: responseHeaders,
  });
}

export default {
  fetch(request, environment) {
    return proxyCustomDomainRequest(request, environment);
  },
};
