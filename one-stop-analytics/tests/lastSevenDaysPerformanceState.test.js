import assert from "node:assert/strict";
import test from "node:test";

import { fetchLastSevenDaysPerformance } from "../app/services/dashboard.js";
import {
  activateWithKeyboard,
  comparisonPresentation,
  focusDailyPerformance,
  formatShortDate,
} from "../app/utils/lastSevenDaysPerformance.js";

test("formats all seven UTC date labels consistently", () => {
  const labels = [7, 8, 9, 10, 11, 12, 13].map((day) =>
    formatShortDate(`2026-08-${String(day).padStart(2, "0")}`));
  assert.deepEqual(labels, [
    "Aug 7", "Aug 8", "Aug 9", "Aug 10", "Aug 11", "Aug 12", "Aug 13",
  ]);
});

test("formats increase, decline, no-change, and new-activity summaries", () => {
  assert.equal(comparisonPresentation({
    status: "increase", percentage_change: 18.4,
  }).text, "18.4% vs previous 7 days");
  assert.equal(comparisonPresentation({
    status: "decline", percentage_change: -100,
  }).symbol, "â†“");
  assert.equal(comparisonPresentation({
    status: "new_activity", percentage_change: null,
  }).text, "New sales activity");
  assert.equal(comparisonPresentation({
    status: "no_change", current_total_sales: 0,
  }).text, "No sales in either period");
});

test("keyboard activation supports Enter and Space", () => {
  let activations = 0;
  const event = { key: "Enter", preventDefault() {} };
  activateWithKeyboard(event, () => { activations += 1; });
  event.key = " ";
  activateWithKeyboard(event, () => { activations += 1; });
  event.key = "Escape";
  activateWithKeyboard(event, () => { activations += 1; });
  assert.equal(activations, 2);
});

test("daily interaction scrolls, focuses, and respects reduced motion", () => {
  const calls = [];
  const element = {
    scrollIntoView(options) { calls.push(options); },
    focus(options) { calls.push(options); },
  };
  focusDailyPerformance(element, () => ({ matches: true }));
  assert.equal(calls[0].behavior, "auto");
  assert.deepEqual(calls[1], { preventScroll: true });
});

test("fixed-window request forwards non-date filters and excludes custom dates", async () => {
  const originalFetch = global.fetch;
  let requestedUrl = "";
  global.fetch = async (url) => {
    requestedUrl = url;
    return { ok: true, json: async () => ({ period: {} }) };
  };
  try {
    await fetchLastSevenDaysPerformance({
      startDate: "2020-01-01",
      endDate: "2020-01-02",
      orderStatuses: ["PAID"],
      fulfillmentStatuses: ["FULFILLED"],
      salesChannels: ["web"],
    });
  } finally {
    global.fetch = originalFetch;
  }
  assert.match(requestedUrl, /financial_status=PAID/);
  assert.match(requestedUrl, /fulfillment_status=FULFILLED/);
  assert.match(requestedUrl, /sales_channel=web/);
  assert.doesNotMatch(requestedUrl, /start_date|end_date|2020/);
});
