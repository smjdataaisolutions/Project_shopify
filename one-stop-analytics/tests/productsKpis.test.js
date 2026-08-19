import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildProductKpisUrl } from "../app/services/products.js";


test("builds the Product KPI URL with every approved filter", () => {
  assert.equal(buildProductKpisUrl(), "/api/products/kpis");
  const url = buildProductKpisUrl({
    startDate: "2026-08-01",
    endDate: "2026-08-19",
    productTypes: ["Snowboard", "Gift Card"],
    vendors: ["Snowdevil"],
    statuses: ["active", "archived"],
  });
  const parameters = new URL(url, "http://localhost").searchParams;
  assert.equal(parameters.get("start_date"), "2026-08-01");
  assert.equal(parameters.get("end_date"), "2026-08-19");
  assert.deepEqual(parameters.getAll("product_type"), ["Snowboard", "Gift Card"]);
  assert.deepEqual(parameters.getAll("vendor"), ["Snowdevil"]);
  assert.deepEqual(parameters.getAll("status"), ["active", "archived"]);
});

test("renders exactly the four approved Product KPI definitions", () => {
  const route = readFileSync("app/routes/app.products.jsx", "utf8");
  const labels = [
    "Total Products",
    "Total Variants",
    "Top Selling Product",
    "Products With No Sales",
  ];

  for (const label of labels) assert.ok(route.includes(`label: "${label}"`));
  assert.equal((route.match(/\n {6}id: "/g) || []).length, 4);
  for (const excluded of [
    "Products Sold",
    "Units Sold",
    "Product Revenue",
    "Avg. Revenue / Product",
    "Low Stock",
    "Out of Stock",
    "Inventory Value",
  ])
    assert.ok(!route.includes(`label: "${excluded}"`));
});

test("uses shared Polaris patterns and handles every Product KPI state", () => {
  const route = readFileSync("app/routes/app.products.jsx", "utf8");

  assert.ok(route.includes("<ProductFilters"));
  assert.ok(route.includes("AppliedProductFilters"));
  assert.ok(
    route.indexOf("<AppliedProductFilters") <
      route.indexOf('className={`${styles.overviewLayout}'),
  );
  assert.ok(route.includes("<KPICard"));
  assert.ok(route.includes("Loading product metrics"));
  assert.ok(route.includes("No products found"));
  assert.ok(route.includes("No product sales found"));
  assert.ok(route.includes("Unable to load products"));
  assert.ok(route.includes("Try again"));
  assert.ok(route.includes("styles.productKpiGrid"));
  const dashboardStyles = readFileSync(
    "app/components/dashboard/dashboard.module.css",
    "utf8",
  );
  const cardStyles = readFileSync(
    "app/components/dashboard/kpiCard.module.css",
    "utf8",
  );
  assert.ok(dashboardStyles.includes("repeat(4, minmax(0, 1fr))"));
  assert.ok(cardStyles.includes("width: 3.25rem"));
  assert.ok(!route.includes("Coming soon"));
});

test("top product displays its image on the right without changing existing cards", () => {
  const route = readFileSync("app/routes/app.products.jsx", "utf8");
  const card = readFileSync("app/components/dashboard/KPICard.jsx", "utf8");

  assert.ok(route.includes("units sold`"));
  assert.ok(route.includes('value: topProduct?.product_name || "—"'));
  assert.ok(route.includes("imageUrl: topProduct?.image_url || null"));
  assert.ok(route.includes("imageAlt: topProduct ? topProduct.product_name : null"));
  assert.ok(card.includes("supportingText"));
  assert.ok(card.includes("supportingText ?"));
  assert.ok(card.includes("styles.productImage"));
  assert.ok(card.includes("styles.imagePlaceholder"));
});

test("requests KPI data with approved filters and disables response caching", () => {
  const route = readFileSync("app/routes/app.products.jsx", "utf8");
  const service = readFileSync("app/services/products.js", "utf8");
  const filters = readFileSync(
    "app/components/products/ProductFilters.jsx",
    "utf8",
  );

  assert.ok(route.includes("fetchProductKpis(filters)"));
  for (const heading of ["Date range", "Product type", "Vendor", "Status"])
    assert.ok(filters.includes(`title="${heading}"`));
  assert.ok(filters.includes("Active"));
  assert.ok(filters.includes("Archived"));
  assert.ok(filters.includes("Clear all"));
  assert.ok(filters.includes("Collapse product filters"));
  assert.ok(route.includes("Expand product filters"));
  assert.ok(service.includes('cache: "no-store"'));
});
