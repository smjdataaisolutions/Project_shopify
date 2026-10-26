import assert from "node:assert/strict";
import test from "node:test";

import {
  focusDailyPerformance,
  getHighlightDestination,
  getHighlightPresentation,
} from "../app/utils/businessHighlights.js";

test("maps all merchant-facing highlight states to accessible text", () => {
  assert.equal(getHighlightPresentation("positive").label, "Positive");
  assert.equal(getHighlightPresentation("attention").label, "Attention");
  assert.equal(getHighlightPresentation("stable").label, "Stable");
  assert.equal(getHighlightPresentation("unavailable").label, "Unavailable");
});

test("uses supported product and inventory destinations", () => {
  assert.equal(
    getHighlightDestination("product_sales_concentration"),
    "/app/products",
  );
  assert.equal(getHighlightDestination("inventory_exposure"), "/app/inventory");
});

test("smoothly scrolls and moves keyboard focus to daily performance", () => {
  const calls = [];
  const element = {
    scrollIntoView: (options) => calls.push(["scroll", options]),
    focus: (options) => calls.push(["focus", options]),
  };

  assert.equal(focusDailyPerformance(element, () => ({ matches: false })), true);
  assert.equal(calls[0][1].behavior, "smooth");
  assert.deepEqual(calls[1], ["focus", { preventScroll: true }]);
});

test("respects reduced motion while retaining focus management", () => {
  const calls = [];
  const element = {
    scrollIntoView: (options) => calls.push(options),
    focus: () => calls.push("focused"),
  };

  focusDailyPerformance(element, () => ({ matches: true }));
  assert.equal(calls[0].behavior, "auto");
  assert.equal(calls[1], "focused");
});
