import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildProductPerformanceUrl } from "../app/services/products.js";
import {
  getNextProductPerformanceSort,
  getProductPerformanceState,
} from "../app/utils/productPerformance.js";

const route = readFileSync("app/routes/app.products.jsx", "utf8");
const component = readFileSync(
  "app/components/products/ProductPerformanceTable.jsx",
  "utf8",
);
const styles = readFileSync(
  "app/components/products/ProductPerformanceTable.module.css",
  "utf8",
);

test("builds a filtered searched sorted paginated Product performance URL", () => {
  const url = buildProductPerformanceUrl({
    filters: {
      startDate: "2026-08-01",
      endDate: "2026-08-19",
      productTypes: ["Shirts"],
      vendors: ["Acme"],
      statuses: ["active"],
    },
    page: 2,
    pageSize: 10,
    search: "red rose & gift",
    sortBy: "revenue",
    sortDirection: "asc",
  });
  const parameters = new URL(url, "http://localhost").searchParams;
  assert.equal(parameters.get("start_date"), "2026-08-01");
  assert.equal(parameters.get("end_date"), "2026-08-19");
  assert.deepEqual(parameters.getAll("product_type"), ["Shirts"]);
  assert.deepEqual(parameters.getAll("vendor"), ["Acme"]);
  assert.deepEqual(parameters.getAll("status"), ["active"]);
  assert.equal(parameters.get("page"), "2");
  assert.equal(parameters.get("page_size"), "10");
  assert.equal(parameters.get("search"), "red rose & gift");
  assert.equal(parameters.get("sort_by"), "revenue");
  assert.equal(parameters.get("sort_direction"), "asc");
});

test("renders exactly eight Product performance columns below the charts", () => {
  for (const label of [
    "Product",
    "Status",
    "Units Sold",
    "Revenue",
    "Orders",
    "Inventory",
    "Sales Velocity",
    "Performance",
  ]) {
    assert.ok(component.includes(`["${label}"`));
  }
  assert.equal((component.match(/^ {2}\["/gm) || []).length, 8);
  assert.ok(route.includes("<ProductPerformanceTable"));
  assert.ok(
    route.indexOf("<ProductPerformanceTable") >
      route.indexOf("<ProductSalesPerformanceCharts"),
  );
});

test("supports thumbnails badges search server sorting and 10-row pagination", () => {
  assert.ok(component.includes("const PAGE_SIZE = 10"));
  assert.ok(component.includes('useState("units_sold")'));
  assert.ok(component.includes('useState("desc")'));
  assert.ok(component.includes('label="Search products"'));
  assert.ok(component.includes("fetchProductPerformance"));
  assert.ok(component.includes("item.image_url"));
  assert.ok(component.includes("No image"));
  assert.ok(component.includes("PRODUCT_STATUS_PRESENTATION"));
  assert.ok(component.includes("PRODUCT_PERFORMANCE_PRESENTATION"));
  assert.ok(component.includes("hasPreviousPage"));
  assert.ok(component.includes("hasNextPage"));
  assert.ok(styles.includes("overflow-x: auto"));
  assert.ok(styles.includes("text-overflow: ellipsis"));
});

test("handles table states and sort toggling", () => {
  assert.equal(
    getProductPerformanceState({ isLoading: true, result: null }),
    "loading",
  );
  assert.equal(
    getProductPerformanceState({ error: "failed", result: null }),
    "error",
  );
  assert.equal(
    getProductPerformanceState({ result: { items: [] }, search: "rose" }),
    "empty_search",
  );
  assert.equal(
    getProductPerformanceState({ result: { items: [] }, search: "" }),
    "empty",
  );
  assert.equal(
    getProductPerformanceState({ result: { items: [{}] } }),
    "ready",
  );
  assert.deepEqual(
    getNextProductPerformanceSort("units_sold", "desc", "units_sold"),
    { sortBy: "units_sold", sortDirection: "asc" },
  );
  assert.deepEqual(
    getNextProductPerformanceSort("units_sold", "asc", "revenue"),
    { sortBy: "revenue", sortDirection: "desc" },
  );
  assert.ok(component.includes("No products found for the selected filters."));
  assert.ok(component.includes("Unable to load product performance data."));
  assert.ok(component.includes("Try again"));
});
