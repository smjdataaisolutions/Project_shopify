import assert from "node:assert/strict";
import test from "node:test";

import { getDailyStorePerformanceState } from "../app/utils/dailyStorePerformance.js";

test("shows loading while the initial request is pending", () => {
  assert.equal(
    getDailyStorePerformanceState({
      isLoading: true,
      result: null,
      error: null,
    }),
    "loading",
  );
});

test("shows a retryable error when the request fails", () => {
  assert.equal(
    getDailyStorePerformanceState({
      isLoading: false,
      result: null,
      error: new Error("request failed"),
    }),
    "error",
  );
});

test("shows the empty state when no daily rows match", () => {
  assert.equal(
    getDailyStorePerformanceState({
      isLoading: false,
      result: { items: [] },
      error: null,
    }),
    "empty",
  );
});

test("shows the table when daily rows are available", () => {
  assert.equal(
    getDailyStorePerformanceState({
      isLoading: false,
      result: { items: [{ date: "2026-08-12" }] },
      error: null,
    }),
    "ready",
  );
});
