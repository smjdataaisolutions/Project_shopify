import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildOrderPerformanceUrl } from "../app/services/orders.js";
import {
  formatOrderDate,
  getNextOrderPerformanceSort,
  getOrderPerformanceState,
} from "../app/utils/orderPerformanceInsights.js";

test("builds a filtered, searched, sorted, paginated performance URL", () => {
  const url = buildOrderPerformanceUrl({
    filters: {
      startDate: "2026-08-01",
      endDate: "2026-08-17",
      orderStatuses: ["open"],
      fulfillmentStatuses: ["FULFILLED"],
      paymentStatuses: ["PAID"],
    },
    page: 2,
    pageSize: 10,
    search: " #1001 ",
    sortBy: "fulfillment_health",
    sortDirection: "asc",
  });

  assert.ok(url.startsWith("/api/orders/performance-insights?"));
  const parameters = new URLSearchParams(url.split("?")[1]);
  assert.equal(parameters.get("start_date"), "2026-08-01");
  assert.equal(parameters.get("order_status"), "open");
  assert.equal(parameters.get("fulfillment_status"), "FULFILLED");
  assert.equal(parameters.get("payment_status"), "PAID");
  assert.equal(parameters.get("page"), "2");
  assert.equal(parameters.get("page_size"), "10");
  assert.equal(parameters.get("search"), "#1001");
  assert.equal(parameters.get("sort_by"), "fulfillment_health");
  assert.equal(parameters.get("sort_direction"), "asc");
});

test("supports loading, error, filter-empty, search-empty, and ready states", () => {
  assert.equal(
    getOrderPerformanceState({ isLoading: true, result: null, error: null, search: "" }),
    "loading",
  );
  assert.equal(
    getOrderPerformanceState({ isLoading: false, result: null, error: "failed", search: "" }),
    "error",
  );
  assert.equal(
    getOrderPerformanceState({ isLoading: false, result: { items: [] }, error: null, search: "" }),
    "empty",
  );
  assert.equal(
    getOrderPerformanceState({ isLoading: false, result: { items: [] }, error: null, search: "#9" }),
    "empty_search",
  );
  assert.equal(
    getOrderPerformanceState({ isLoading: false, result: { items: [{}] }, error: null, search: "" }),
    "ready",
  );
});

test("toggles same-column sorting and defaults a new column descending", () => {
  assert.deepEqual(
    getNextOrderPerformanceSort("order_date", "desc", "order_date"),
    { sortBy: "order_date", sortDirection: "asc" },
  );
  assert.deepEqual(
    getNextOrderPerformanceSort("order_date", "asc", "fulfillment_status"),
    { sortBy: "fulfillment_status", sortDirection: "desc" },
  );
});

test("formats timestamps in UTC without local-date drift", () => {
  assert.equal(formatOrderDate("2026-08-12T23:30:00Z", "en-US"), "Aug 12, 2026");
});

test("renders the required table after Orders Analytics with all states and actions", () => {
  const route = readFileSync("app/routes/app.orders.jsx", "utf8");
  const component = readFileSync(
    "app/components/orders/OrderPerformanceInsights.jsx",
    "utf8",
  );
  const stylesheet = readFileSync(
    "app/components/orders/orderPerformanceInsights.module.css",
    "utf8",
  );
  assert.ok(
    route.indexOf('heading="Order Fulfillment Details"') >
      route.indexOf('heading="Orders Analytics"'),
  );
  for (const heading of [
    "Order",
    "Order Date",
    "Units Ordered",
    "Order Progress",
    "Fulfillment Health",
    "Timeline",
    "Action",
  ]) {
    assert.ok(component.includes(`"${heading}"`));
  }
  assert.ok(component.includes("Try again"));
  assert.ok(component.includes("No orders match"));
  assert.ok(component.includes("View order"));
  assert.ok(component.includes("View timeline"));
  assert.ok(component.includes("OrderTimelineModal"));
  assert.ok(
    component.includes(
      "Track order fulfilment progress and identify orders that require attention.",
    ),
  );
  for (const removedHeading of [
    "Gross sales",
    "Discount Amount",
    "Refund Amount",
    "Net Revenue",
    "Order Health",
    "Fulfillment Status",
  ]) {
    assert.ok(!component.includes(`"${removedHeading}"`));
  }
  assert.ok(!component.includes("Order health guide"));
  assert.ok(component.includes("ORDER_PROGRESS_TONE"));
  assert.ok(component.includes("FULFILLMENT_HEALTH_PRESENTATION"));
  assert.ok(component.includes("hasPreviousPage"));
  assert.ok(component.includes("hasNextPage"));
  assert.ok(stylesheet.includes("overflow-x: auto"));
  assert.ok(stylesheet.includes("min-width: 66rem"));
});
