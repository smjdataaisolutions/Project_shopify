import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { StaticRouter } from "react-router";
import { AppProvider } from "@shopify/shopify-app-react-router/react";

const routePath = new URL(
  "../app/routes/auth.login/route.jsx",
  import.meta.url,
);

test("public login route delegates immediately and never accepts a merchant-entered shop domain", async () => {
  const source = await readFile(routePath, "utf8");

  assert.doesNotMatch(source, /<Form\b/);
  assert.doesNotMatch(source, /name=["']shop["']/);
  assert.doesNotMatch(source, /example\.myshopify\.com/);
  assert.doesNotMatch(source, /export\s+const\s+action/);
  assert.match(
    source,
    /export const loader[\s\S]*await login\(request\)[\s\S]*return \{ errors \}/,
  );
  assert.match(source, /Shopify-owned surface/);
});

test("embedded AppProvider injects one ordered App Bridge script", () => {
  const markup = renderToStaticMarkup(
    React.createElement(
      StaticRouter,
      { location: "/app" },
      React.createElement(
        AppProvider,
        { embedded: true, apiKey: "test-client-id" },
        React.createElement("main", null, "OneStop Analytics"),
      ),
    ),
  );

  const appBridgeUrl =
    "https://cdn.shopify.com/shopifycloud/app-bridge.js";
  const polarisUrl = "https://cdn.shopify.com/shopifycloud/polaris.js";

  assert.equal(markup.split(appBridgeUrl).length - 1, 1);
  assert.match(markup, /data-api-key="test-client-id"/);
  assert.ok(markup.indexOf(appBridgeUrl) < markup.indexOf(polarisUrl));
});

test("root document leaves App Bridge injection to AppProvider", async () => {
  const rootPath = new URL("../app/root.jsx", import.meta.url);
  const source = await readFile(rootPath, "utf8");

  assert.doesNotMatch(source, /shopifycloud\/app-bridge\.js/);
  assert.doesNotMatch(source, /name=["']shopify-api-key["']/);
  assert.ok(source.indexOf("<Outlet />") < source.indexOf("<Scripts />"));
});
