import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildOrderTimelineUrl } from "../app/services/orders.js";
import {
  formatTimelineAmount,
  formatTimelineDate,
  formatTimelineStatus,
  getOrderTimelineState,
  sortOrderTimelineEvents,
} from "../app/utils/orderTimeline.js";

test("builds a safely encoded Shopify order timeline URL", () => {
  assert.equal(
    buildOrderTimelineUrl("gid://shopify/Order/301"),
    "/api/orders/gid%3A%2F%2Fshopify%2FOrder%2F301/timeline",
  );
});

test("sorts timeline events oldest to newest without mutating the response", () => {
  const events = [
    { event_type: "refund_recorded", occurred_at: "2026-08-03T10:00:00Z" },
    { event_type: "order_created", occurred_at: "2026-08-01T09:00:00Z" },
    { event_type: "order_processed", occurred_at: "2026-08-01T09:05:00Z" },
  ];
  const sorted = sortOrderTimelineEvents(events);
  assert.deepEqual(
    sorted.map((event) => event.event_type),
    ["order_created", "order_processed", "refund_recorded"],
  );
  assert.equal(events[0].event_type, "refund_recorded");
});

test("supports loading, stale protection, error, empty, and ready states", () => {
  assert.equal(
    getOrderTimelineState({ isLoading: true, result: null, error: null, orderId: "a" }),
    "loading",
  );
  assert.equal(
    getOrderTimelineState({ isLoading: false, result: null, error: "failed", orderId: "a" }),
    "error",
  );
  assert.equal(
    getOrderTimelineState({ isLoading: false, result: { order_id: "b", events: [{}] }, error: null, orderId: "a" }),
    "loading",
  );
  assert.equal(
    getOrderTimelineState({ isLoading: false, result: { order_id: "a", events: [] }, error: null, orderId: "a" }),
    "empty",
  );
  assert.equal(
    getOrderTimelineState({ isLoading: false, result: { order_id: "a", events: [{}] }, error: null, orderId: "a" }),
    "ready",
  );
});

test("formats timeline dates, amounts, and status labels", () => {
  assert.match(formatTimelineDate("2026-08-18T10:25:00Z", "en-US"), /Aug 18, 2026/);
  assert.equal(formatTimelineAmount(500, "USD", "en-US"), "$500.00");
  assert.equal(formatTimelineStatus("partially_refunded"), "Partially Refunded");
  assert.equal(formatTimelineStatus(null), "Unknown");
});

test("uses a Polaris modal with accessible, retryable, scrollable timeline states", () => {
  const table = readFileSync(
    "app/components/orders/OrderPerformanceInsights.jsx",
    "utf8",
  );
  const modal = readFileSync(
    "app/components/orders/OrderTimelineModal.jsx",
    "utf8",
  );
  const stylesheet = readFileSync(
    "app/components/orders/orderTimelineModal.module.css",
    "utf8",
  );

  assert.ok(table.indexOf('["Timeline", null]') < table.indexOf('["Action", null]'));
  assert.ok(table.includes("View timeline for ${item.order_name}"));
  assert.ok(table.includes("key={timelineOrder.order_id}"));
  assert.ok(modal.includes("<s-modal"));
  assert.ok(modal.includes("showOverlay"));
  assert.ok(modal.includes("onHide={onClose}"));
  assert.ok(modal.includes("setResult(null)"));
  assert.ok(modal.includes("Try again"));
  assert.ok(modal.includes("No timestamped events are available"));
  assert.ok(modal.includes("Exact time unavailable"));
  assert.ok(!modal.includes("window.open"));
  assert.ok(stylesheet.includes("overflow-y: auto"));
  assert.ok(stylesheet.includes("max-height: 24rem"));
  assert.ok(stylesheet.includes("display: grid"));
});
