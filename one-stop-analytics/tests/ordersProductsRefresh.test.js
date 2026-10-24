import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ordersRoute = readFileSync("app/routes/app.orders.jsx", "utf8");
const productsRoute = readFileSync("app/routes/app.products.jsx", "utf8");
const productCharts = readFileSync(
  "app/components/products/ProductSalesPerformanceCharts.jsx",
  "utf8",
);
const productTable = readFileSync(
  "app/components/products/ProductPerformanceTable.jsx",
  "utf8",
);

for (const [page, route] of [
  ["Orders", ordersRoute],
  ["Products", productsRoute],
]) {
  test(`${page} navigation shows the last update time and refresh action`, () => {
    assert.ok(route.includes("Last updated:"));
    assert.ok(route.includes("formatOverviewUpdatedAt(lastUpdatedAt)"));
    assert.ok(route.includes('icon="refresh"'));
    assert.ok(route.includes(`Refresh ${page} analytics`));
    assert.ok(route.includes("setLastUpdatedAt(new Date())"));
  });
}

test("Products refresh reloads KPIs charts and table", () => {
  assert.ok(productsRoute.includes("refreshKey={requestVersion}"));
  assert.ok(productCharts.includes("[filters, refreshKey, requestVersion]"));
  assert.ok(productTable.includes("refreshKey, requestVersion"));
});
