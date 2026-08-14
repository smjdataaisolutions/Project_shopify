import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  formatDailySalesDate,
  getDailySalesBreakdownState,
  getNextDailySalesSort,
} from "../app/utils/dailySalesBreakdown.js";

test("supports loading, error, empty, and ready table states", () => {
  assert.equal(
    getDailySalesBreakdownState({ isLoading: true, result: null, error: null }),
    "loading",
  );
  assert.equal(
    getDailySalesBreakdownState({
      isLoading: false,
      result: null,
      error: "failed",
    }),
    "error",
  );
  assert.equal(
    getDailySalesBreakdownState({
      isLoading: false,
      result: { items: [] },
      error: null,
    }),
    "empty",
  );
  assert.equal(
    getDailySalesBreakdownState({
      isLoading: false,
      result: { items: [{ date: "2026-08-12" }] },
      error: null,
    }),
    "ready",
  );
});

test("uses date descending by default and toggles sortable columns", () => {
  assert.deepEqual(getNextDailySalesSort("date", "desc", "date"), {
    sortBy: "date",
    sortDirection: "asc",
  });
  assert.deepEqual(getNextDailySalesSort("date", "asc", "gross_sales"), {
    sortBy: "gross_sales",
    sortDirection: "desc",
  });
});

test("formats a processed calendar date without local-time drift", () => {
  assert.equal(formatDailySalesDate("2026-08-12", "en-US"), "Aug 12, 2026");
});

test("renders the required columns below Action needed without Customers", () => {
  const route = readFileSync("app/routes/app.sales.jsx", "utf8");
  const component = readFileSync(
    "app/components/sales/DailySalesBreakdown.jsx",
    "utf8",
  );
  const actionIndex = route.indexOf('heading="Action needed"');
  const tableIndex = route.indexOf('heading="Daily Sales Breakdown"');
  assert.ok(actionIndex >= 0 && tableIndex > actionIndex);
  for (const heading of [
    "Date",
    "Gross sales",
    "Discounts",
    "Returns/refunds",
    "Net sales",
    "Shipping",
    "Tax",
    "Total sales",
    "Orders",
    "Average order value",
  ]) {
    assert.ok(component.includes(`"${heading}"`));
  }
  assert.ok(!component.includes("Customers"));
});

test("keeps pagination, filters, totals, currency, and horizontal overflow wired", () => {
  const component = readFileSync(
    "app/components/sales/DailySalesBreakdown.jsx",
    "utf8",
  );
  const stylesheet = readFileSync(
    "app/components/sales/dailySalesBreakdown.module.css",
    "utf8",
  );
  assert.ok(component.includes("useEffect(() => setPage(1), [filters])"));
  assert.ok(component.includes("Intl.NumberFormat"));
  assert.ok(component.includes("result?.currency"));
  assert.ok(component.includes("renderValue(summary"));
  assert.ok(component.includes("hasPreviousPage"));
  assert.ok(component.includes("hasNextPage"));
  assert.ok(stylesheet.includes("overflow-x: auto"));
  assert.ok(stylesheet.includes("min-width: 90rem"));
  assert.ok(stylesheet.includes("justify-content: flex-start"));
  assert.ok(stylesheet.includes("text-align: left"));
});

test("orders the Sales KPI cards into the requested two rows", () => {
  const route = readFileSync("app/routes/app.sales.jsx", "utf8");
  const labels = [...route.matchAll(/label: "([^"]+)"/g)].map(
    (match) => match[1],
  );
  assert.deepEqual(labels.slice(0, 8), [
    "Gross sales",
    "Discounts",
    "Returns/refunds",
    "Net sales",
    "Shipping",
    "Taxes",
    "Orders",
    "Total sales",
  ]);
  assert.ok(!labels.includes("Average order value"));
  assert.ok(route.includes("styles.salesKpiGrid"));
  assert.ok(route.includes("summary.returns_refunds ?? 0"));
  assert.equal(route.match(/"Definition:/g)?.length, 8);
  assert.equal(route.match(/"Formula:/g)?.length, 8);
});

test("shows PostgreSQL synchronization time and refreshes every Sales section", () => {
  const route = readFileSync("app/routes/app.sales.jsx", "utf8");
  assert.ok(route.includes("Last updated:"));
  assert.ok(route.includes("formatOverviewUpdatedAt(lastUpdatedAt)"));
  assert.ok(route.includes('icon="refresh"'));
  assert.ok(route.includes("Refresh Sales analytics"));
  assert.ok(route.includes("trend:${requestVersion}"));
  assert.ok(route.includes("actions:${requestVersion}"));
  assert.ok(route.includes("breakdown:${requestVersion}"));
});

test("renders removable applied filters below Sales navigation", () => {
  const route = readFileSync("app/routes/app.sales.jsx", "utf8");
  const filters = readFileSync(
    "app/components/sales/SalesFilters.jsx",
    "utf8",
  );
  const navigationEnd = route.indexOf("</AnalyticsTopNavigation>");
  const appliedFilters = route.indexOf("<AppliedSalesFilters");
  const layout = route.indexOf("styles.overviewLayout");
  assert.ok(navigationEnd >= 0 && appliedFilters > navigationEnd);
  assert.ok(layout > appliedFilters);
  assert.ok(filters.includes("Applied filters:"));
  assert.ok(filters.includes("Sales channel:"));
  assert.ok(filters.includes("Order status:"));
  assert.ok(filters.includes("Currency:"));
  assert.ok(filters.includes("formatDateRange(filters)"));
});
