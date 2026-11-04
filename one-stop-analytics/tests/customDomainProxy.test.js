import assert from "node:assert/strict";
import test from "node:test";

import { proxyCustomDomainRequest } from "../cloudflare/custom-domain-worker/src/index.js";

test("proxies the custom hostname to the fixed Cloud Run frontend", async () => {
  let forwarded;
  const response = await proxyCustomDomainRequest(
    new Request("https://app.smjdataai.com/auth/callback?code=test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: '{"ok":true}',
    }),
    {},
    async (request, options) => {
      forwarded = { request, options };
      return new Response("ok", { status: 200 });
    },
  );

  assert.equal(response.status, 200);
  assert.equal(
    forwarded.request.url,
    "https://smj-shopify-frontend-876969185947.us-east5.run.app/auth/callback?code=test",
  );
  assert.equal(forwarded.request.headers.get("x-forwarded-host"), "app.smjdataai.com");
  assert.equal(forwarded.request.headers.get("x-forwarded-proto"), "https");
  assert.equal(await forwarded.request.text(), '{"ok":true}');
  assert.equal(forwarded.options.redirect, "manual");
});

test("rejects another hostname and an arbitrary configured origin", async () => {
  const wrongHost = await proxyCustomDomainRequest(
    new Request("https://smjdataai.com/"),
    {},
    async () => {
      throw new Error("must not fetch");
    },
  );
  assert.equal(wrongHost.status, 421);

  await assert.rejects(
    proxyCustomDomainRequest(
      new Request("https://app.smjdataai.com/"),
      { CLOUD_RUN_ORIGIN: "https://attacker.example" },
      async () => new Response(),
    ),
    /not an approved frontend origin/,
  );
});

test("rewrites Cloud Run redirects back to the public custom hostname", async () => {
  const response = await proxyCustomDomainRequest(
    new Request("https://app.smjdataai.com/"),
    {},
    async () =>
      new Response(null, {
        status: 302,
        headers: {
          Location:
            "https://smj-shopify-frontend-876969185947.us-east5.run.app/app?shop=test",
        },
      }),
  );
  assert.equal(
    response.headers.get("location"),
    "https://app.smjdataai.com/app?shop=test",
  );
});

test("allows only the exact configured workers.dev preview hostname", async () => {
  const previewHostname =
    "smj-shopify-frontend-domain-proxy.smjdataaisolutions.workers.dev";
  const response = await proxyCustomDomainRequest(
    new Request(`https://${previewHostname}/app`),
    { PUBLIC_HOSTNAME: previewHostname },
    async () => new Response("preview", { status: 200 }),
  );
  assert.equal(response.status, 200);

  await assert.rejects(
    proxyCustomDomainRequest(
      new Request("https://app.smjdataai.com/"),
      { PUBLIC_HOSTNAME: "attacker.example" },
      async () => new Response(),
    ),
    /PUBLIC_HOSTNAME is not approved/,
  );
});
