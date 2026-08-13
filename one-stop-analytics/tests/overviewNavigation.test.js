import assert from "node:assert/strict";
import test from "node:test";

import {
  formatOverviewUpdatedAt,
  getInventoryNavigationState,
  getOverviewKpiDestination,
} from "../app/utils/overviewNavigation.js";

test("maps every Overview KPI to its approved destination", () => {
  assert.equal(getOverviewKpiDestination("total_products"), "/app/products");
  assert.equal(
    getOverviewKpiDestination("total_variants"),
    "/app/inventory?level=variant",
  );
  assert.equal(
    getOverviewKpiDestination("low_stock_products"),
    "/app/inventory?level=product&inventory_status=low_stock",
  );
  assert.equal(
    getOverviewKpiDestination("out_of_stock_products"),
    "/app/inventory?level=product&inventory_status=out_of_stock",
  );
  assert.equal(getOverviewKpiDestination("total_orders"), "/app/orders");
  assert.equal(getOverviewKpiDestination("total_revenue"), "/app/sales");
  assert.equal(getOverviewKpiDestination("units_sold"), "/app/sales");
  assert.equal(getOverviewKpiDestination("average_order_value"), "/app/sales");
});

test("validates Inventory level and status query state", () => {
  const valid = getInventoryNavigationState(
    new URLSearchParams("level=product&inventory_status=low_stock"),
  );
  assert.deepEqual(valid, {
    level: "product",
    inventoryStatuses: ["low_stock"],
  });

  const invalid = getInventoryNavigationState(
    new URLSearchParams("level=unsupported&inventory_status=not-real"),
  );
  assert.deepEqual(invalid, { level: "variant", inventoryStatuses: [] });
});

test("formats successful refresh time and handles the initial state", () => {
  assert.equal(formatOverviewUpdatedAt(null), "â€”");
  const formatted = formatOverviewUpdatedAt(new Date("2026-08-13T06:05:00Z"));
  assert.match(formatted, /Aug 13, 2026/);
  assert.match(formatted, /AM|PM/);
});
