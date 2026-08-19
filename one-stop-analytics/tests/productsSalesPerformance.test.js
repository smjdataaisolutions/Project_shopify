import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildProductSalesPerformanceUrl } from "../app/services/products.js";

const route = readFileSync("app/routes/app.products.jsx", "utf8");
const component = readFileSync(
  "app/components/products/ProductSalesPerformanceCharts.jsx",
  "utf8",
);
const styles = readFileSync(
  "app/components/products/ProductSalesPerformanceCharts.module.css",
  "utf8",
);

test("builds the sales-performance URL with all Product filters", () => {
  assert.equal(
    buildProductSalesPerformanceUrl(),
    "/api/products/sales-performance",
  );
  const url = buildProductSalesPerformanceUrl({
    startDate: "2026-08-01",
    endDate: "2026-08-19",
    productTypes: ["Snowboard", "Gift Card"],
    vendors: ["Snowdevil", "Acme"],
    statuses: ["active", "archived"],
  });
  const parameters = new URL(url, "http://localhost").searchParams;
  assert.equal(parameters.get("start_date"), "2026-08-01");
  assert.equal(parameters.get("end_date"), "2026-08-19");
  assert.deepEqual(parameters.getAll("product_type"), [
    "Snowboard",
    "Gift Card",
  ]);
  assert.deepEqual(parameters.getAll("vendor"), ["Snowdevil", "Acme"]);
  assert.deepEqual(parameters.getAll("status"), ["active", "archived"]);
});

test("places Product Sales Performance below the Product KPI section", () => {
  assert.ok(route.includes("<ProductSalesPerformanceCharts"));
  assert.ok(route.includes("refreshKey={requestVersion}"));
  assert.ok(
    route.indexOf("<ProductSalesPerformanceCharts") >
      route.indexOf("styles.productKpiGrid"),
  );
});

test("renders the approved Product sales charts without Low Selling Products", () => {
  for (const text of [
    "Product Sales Performance",
    "Top Selling Products",
    "Top 10 products by units sold",
    "Product Name",
    "Units Sold",
    "Sales by Vendor / Product Type",
    "Which vendor or product type generates the most revenue?",
    "Product Revenue Contribution",
    "Products generating the most gross revenue",
    "Revenue",
  ]) {
    assert.ok(component.includes(text));
  }
  assert.ok(component.includes("function VerticalProductBars"));
  assert.ok(component.includes("function RevenueDimensionBars"));
  assert.ok(component.includes("function ProductRevenueBars"));
  assert.ok(!component.includes("function HorizontalProductBars"));
  assert.ok(!component.includes("Low Selling Products"));
  assert.ok(component.includes("<rect"));
  assert.ok(component.includes("<title>{tooltip(item)}</title>"));
  assert.ok(component.includes("item.product_name"));
  assert.ok(component.includes('value="vendor"'));
  assert.ok(component.includes('value="product_type"'));
  assert.ok(component.includes("result?.sales_by_vendor"));
  assert.ok(component.includes("result?.sales_by_product_type"));
  assert.ok(component.includes("result?.product_revenue_contribution"));
  assert.ok(component.includes("result?.currency"));
  assert.ok(component.includes("Math.min(graphWidth, items.length * 80)"));
  assert.ok(component.includes("const startX = pad.left"));
  assert.ok(component.includes("pad.left + usedWidth + pad.right"));
  assert.ok(component.includes("viewBox={`0 0 ${chartWidth} ${height}`}"));
  assert.ok(styles.includes(".dimensionChart"));
  assert.ok(!component.includes(".sort("));
});

test("handles states and uses one three-chart desktop row", () => {
  assert.ok(component.includes("Loading chart..."));
  assert.ok(
    component.includes(
      "No product sales data available for the selected period.",
    ),
  );
  assert.ok(component.includes("Unable to load product sales charts."));
  assert.ok(component.includes("Try again"));
  assert.ok(component.includes("fetchProductSalesPerformance(filters)"));
  assert.ok(styles.includes("repeat(3, minmax(0, 1fr))"));
  assert.ok(styles.includes("@media (max-width: 900px)"));
  assert.ok(styles.includes("grid-template-columns: minmax(0, 1fr)"));
});
