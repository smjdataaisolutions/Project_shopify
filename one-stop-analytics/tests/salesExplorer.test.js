import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  formatExplorerPeriod,
  measuresForDimension,
  normalizeExplorerSelection,
  SALES_EXPLORER_COMPARISONS,
  SALES_EXPLORER_DIMENSIONS,
} from "../app/utils/salesExplorer.js";

test("supports the approved dimension and measure matrix", () => {
  assert.deepEqual(
    measuresForDimension("processed_date").map(({ id }) => id),
    ["revenue", "orders", "units_sold", "average_order_value"],
  );
  assert.deepEqual(
    measuresForDimension("product").map(({ id }) => id),
    ["revenue", "orders", "units_sold"],
  );
  assert.equal(
    normalizeExplorerSelection("product", "average_order_value"),
    "revenue",
  );
});

test("marks Location unavailable instead of fabricating an order relationship", () => {
  const location = SALES_EXPLORER_DIMENSIONS.find(({ id }) => id === "location");
  assert.equal(location.disabled, true);
  assert.match(location.reason, /verified location relationship/);
});

test("exposes every comparison option and formats backend period metadata", () => {
  assert.deepEqual(
    SALES_EXPLORER_COMPARISONS.map(({ id }) => id),
    ["none", "previous_period", "previous_7_days", "previous_30_days"],
  );
  assert.equal(
    formatExplorerPeriod({
      start_date: "2026-08-03",
      end_date: "2026-08-09",
      days: 7,
    }),
    "Aug 3–Aug 9 · 7 days",
  );
});

test("shows visible data labels for every chart type", () => {
  const chart = readFileSync(
    new URL("../app/components/sales/SalesExplorer.jsx", import.meta.url),
    "utf8",
  );
  const css = readFileSync(
    new URL("../app/components/sales/salesExplorer.module.css", import.meta.url),
    "utf8",
  );
  assert.equal((chart.match(/styles\.dataLabel/g) || []).length, 2);
  assert.match(chart, /styles\.barValue/);
  assert.match(css, /\.dataLabel/);
});

test("labels the Y-axis with the selected measure and currency", () => {
  const chart = readFileSync(
    new URL("../app/components/sales/SalesExplorer.jsx", import.meta.url),
    "utf8",
  );
  assert.match(chart, /function measureAxisLabel/);
  assert.equal((chart.match(/measureAxisLabel\(/g) || []).length, 3);
  assert.match(chart, /rotate\(-90\)/);
});

test("replaces the standalone Revenue trend below KPIs", () => {
  const route = readFileSync(
    new URL("../app/routes/app.sales.jsx", import.meta.url),
    "utf8",
  );
  const service = readFileSync(
    new URL("../app/services/sales.js", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(route, /heading="Revenue trend"/);
  assert.doesNotMatch(route, /<RevenueTrend/);
  assert.ok(route.indexOf('heading="Sales overview"') < route.indexOf('heading="Explore Sales"'));
  assert.ok(route.indexOf('heading="Explore Sales"') < route.indexOf('heading="Action needed"'));
  assert.match(service, /\/api\/sales\/chart/);
  assert.match(service, /withSalesFilters\(SALES_CHART_ENDPOINT/);
});

test("renders comparison controls, summaries, and dual-series charts", () => {
  const chart = readFileSync(
    new URL("../app/components/sales/SalesExplorer.jsx", import.meta.url),
    "utf8",
  );
  const service = readFileSync(
    new URL("../app/services/sales.js", import.meta.url),
    "utf8",
  );
  assert.match(chart, /Compare with/);
  assert.match(chart, /comparison_data/);
  assert.match(chart, /comparisonLine/);
  assert.match(chart, /comparisonBar/);
  assert.match(chart, /No previous-period baseline/);
  assert.match(chart, /different lengths/);
  assert.match(chart, /No data available for the comparison period/);
  assert.match(service, /comparison = "none"/);
  assert.match(service, /comparison,/);
});
