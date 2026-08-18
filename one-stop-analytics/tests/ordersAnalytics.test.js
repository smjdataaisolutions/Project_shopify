import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { buildOrderChartsUrl } from "../app/services/orders.js";

test("builds one Orders charts request with every shared filter", () => {
  const parsed = new URL(
    buildOrderChartsUrl({
      startDate: "2026-01-01",
      endDate: "2026-08-17",
      salesChannels: ["web", "pos"],
      orderStatuses: ["cancelled"],
      fulfillmentStatuses: ["FULFILLED"],
      paymentStatuses: ["PAID"],
    }),
    "https://example.test",
  );

  assert.equal(parsed.pathname, "/api/orders/charts");
  assert.equal(parsed.searchParams.get("start_date"), "2026-01-01");
  assert.equal(parsed.searchParams.get("end_date"), "2026-08-17");
  assert.deepEqual(parsed.searchParams.getAll("sales_channel"), ["web", "pos"]);
  assert.deepEqual(parsed.searchParams.getAll("order_status"), ["cancelled"]);
  assert.deepEqual(parsed.searchParams.getAll("fulfillment_status"), [
    "FULFILLED",
  ]);
  assert.deepEqual(parsed.searchParams.getAll("payment_status"), ["PAID"]);
});

test("places exactly four approved charts below the KPI overview", () => {
  const route = readFileSync("app/routes/app.orders.jsx", "utf8");
  const component = readFileSync(
    "app/components/orders/OrdersAnalytics.jsx",
    "utf8",
  );

  assert.ok(
    route.indexOf('heading="Order overview"') <
      route.indexOf('heading="Orders Analytics"'),
  );
  for (const title of [
    "Weekly Orders Trend",
    "Fulfillment Status",
    "Orders by Sales Channel",
    "Total Orders Distribution",
  ]) {
    assert.match(component, new RegExp(`"${title}"`));
  }
  assert.match(component, /fetchOrderCharts\(filters\)/);
  assert.match(component, /role="img"/);
  assert.match(component, /<title>/);
  assert.match(component, /tabIndex="0"/);
  assert.match(component, /showValues/);
  assert.match(component, /title="Weekly Orders Trend"[\s\S]{0,300}showValues/);
  assert.match(component, /number\.format\(items\[index\]\[entry\.key\]\)/);
  assert.match(component, /end\.setUTCDate\(end\.getUTCDate\(\) \+ 6\)/);
  assert.match(component, /startMonth === endMonth/);
  assert.match(component, /dateLabel\(item\.date, granularity\)/);
  assert.match(component, />\s*Week\s*</);
  assert.match(component, /function OrderStatusPie/);
  assert.match(component, /data\.order_status_distribution/);
  assert.match(component, /Total Orders Distribution/);
  assert.match(component, /percentage\.format\(share\)/);
  assert.match(component, /styles\.pieLeader/);
  assert.match(component, /styles\.pieExternalLabel/);
  assert.match(component, /styles\.pieValue/);
  assert.doesNotMatch(component, /styles\.pieLegend/);
  assert.match(component, /r="120"/);
  assert.match(
    component,
    /slice\.label}: \{number\.format\(slice\.value\)}\s*</,
  );
  assert.match(
    component,
    /className=\{styles\.pieValue\}[\s\S]*?percentage\.format\(share\)}%/,
  );
  for (const status of ["Fulfilled", "Unfulfilled", "Cancelled", "Refunded"]) {
    assert.match(component, new RegExp(`${status}: "pie${status}"`));
  }
});

test("contains independent loading, empty, retryable error, and responsive states", () => {
  const component = readFileSync(
    "app/components/orders/OrdersAnalytics.jsx",
    "utf8",
  );
  const css = readFileSync(
    "app/components/orders/ordersAnalytics.module.css",
    "utf8",
  );

  assert.match(component, /Loading chart…/);
  assert.match(component, /No chart data matches the selected filters/);
  assert.match(component, /Try again/);
  assert.match(component, /if \(!data\) return <LoadingCards/);
  assert.match(css, /grid-template-columns: repeat\(2/);
  assert.match(css, /@media \(max-width: 768px\)/);
  assert.match(css, /grid-template-columns: 1fr/);
  assert.match(css, /\.line \{[\s\S]*?fill: none;/);
  assert.match(css, /\.ordersLine \{\s*stroke:[^}]+\}/);
  assert.match(css, /\.point\.ordersLine \{\s*fill:/);
});
