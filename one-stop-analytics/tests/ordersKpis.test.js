import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildOrderKpisUrl } from "../app/services/orders.js";

test("builds one Orders KPI request with shared filters", () => {
  const url = buildOrderKpisUrl({
    startDate: "2026-08-01",
    endDate: "2026-08-17",
    salesChannels: ["web", "pos"],
    orderStatuses: ["open"],
    fulfillmentStatuses: ["FULFILLED"],
    paymentStatuses: ["PAID"],
  });
  const parsed = new URL(url, "https://example.test");

  assert.equal(parsed.pathname, "/api/orders/kpis");
  assert.equal(parsed.searchParams.get("start_date"), "2026-08-01");
  assert.equal(parsed.searchParams.get("end_date"), "2026-08-17");
  assert.deepEqual(parsed.searchParams.getAll("sales_channel"), ["web", "pos"]);
  assert.deepEqual(parsed.searchParams.getAll("order_status"), ["open"]);
  assert.deepEqual(parsed.searchParams.getAll("fulfillment_status"), ["FULFILLED"]);
  assert.deepEqual(parsed.searchParams.getAll("payment_status"), ["PAID"]);
});

test("renders exactly the eight approved Order KPI definitions", () => {
  const route = readFileSync("app/routes/app.orders.jsx", "utf8");
  const labels = [
    "Total Orders",
    "Units Ordered",
    "Unfulfilled Orders",
    "Partially Fulfilled Orders",
    "Fulfilled Orders",
    "Cancelled Orders",
    "Refunded Orders",
    "Fulfillment Rate",
  ];

  for (const label of labels) assert.match(route, new RegExp(`label: "${label}"`));
  assert.equal((route.match(/label: "/g) || []).length, 8);
  assert.match(route, /Intl\.NumberFormat/);
  assert.match(route, /fulfillment_rate\)}%/);
});

test("contains loading, zero-order empty, retryable error, and ready states", () => {
  const route = readFileSync("app/routes/app.orders.jsx", "utf8");

  assert.match(route, /heading="Loading orders"/);
  assert.match(route, /heading="Unable to load orders"/);
  assert.match(route, /Try again/);
  assert.match(route, /kpis\.total_orders === 0/);
  assert.match(route, /heading="No orders found"/);
  assert.match(route, /heading="Order overview"/);
});

test("reuses the date picker and explains unavailable location attribution", () => {
  const filters = readFileSync(
    "app/components/orders/OrdersFilters.jsx",
    "utf8",
  );

  assert.match(filters, /DateRangePicker/);
  assert.match(filters, /heading="Sales channel"/);
  assert.match(filters, /heading="Order status"/);
  assert.match(filters, /heading="Fulfillment status"/);
  assert.match(filters, /heading="Payment status"/);
  assert.match(filters, /title="Location"/);
  assert.match(filters, /do\s+not include fulfillment-location attribution/);
});
