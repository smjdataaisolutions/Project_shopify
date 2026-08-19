/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { fetchProductSalesPerformance } from "../../services/products";
import styles from "./ProductSalesPerformanceCharts.module.css";

const WIDTH = 640;
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

function truncate(value, limit) {
  return value.length > limit ? `${value.slice(0, limit - 3)}...` : value;
}

function tooltip(item) {
  return `Product: ${item.product_name}\nUnits Sold: ${number.format(item.units_sold)}`;
}

function ChartCard({ title, subtitle, controls, children }) {
  return (
    <s-box padding="base" borderWidth="base" borderRadius="base" background="base">
      <article className={styles.card} aria-label={title}>
        <div className={styles.cardHeader}>
          <div>
            <s-heading>{title}</s-heading>
            <s-text tone="subdued">{subtitle}</s-text>
          </div>
          {controls}
        </div>
        {children}
      </article>
    </s-box>
  );
}

function ScreenReaderData({ items }) {
  return (
    <ul className={styles.screenReaderOnly}>
      {items.map((item) => (
        <li key={item.product_id}>
          {item.product_name}: {number.format(item.units_sold)} units sold
        </li>
      ))}
    </ul>
  );
}

function VerticalProductBars({ items }) {
  const height = 320;
  const pad = { top: 28, right: 16, bottom: 88, left: 48 };
  const graphWidth = WIDTH - pad.left - pad.right;
  const graphHeight = height - pad.top - pad.bottom;
  const maximum = Math.max(1, ...items.map((item) => item.units_sold));
  const slot = graphWidth / items.length;
  const barWidth = Math.min(42, slot * 0.64);

  return (
    <div className={styles.chartScroller}>
      <svg
        className={styles.chart}
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label="Top Selling Products by units sold"
      >
        <title>Top Selling Products by units sold</title>
        {[0, 0.5, 1].map((ratio) => {
          const y = pad.top + graphHeight * (1 - ratio);
          return (
            <g key={ratio}>
              <line
                className={styles.gridLine}
                x1={pad.left}
                x2={WIDTH - pad.right}
                y1={y}
                y2={y}
              />
              <text className={styles.axisText} x={pad.left - 8} y={y + 4} textAnchor="end">
                {number.format(maximum * ratio)}
              </text>
            </g>
          );
        })}
        {items.map((item, index) => {
          const barHeight = (item.units_sold / maximum) * graphHeight;
          const x = pad.left + index * slot + (slot - barWidth) / 2;
          const y = pad.top + graphHeight - barHeight;
          const center = x + barWidth / 2;
          return (
            <g key={item.product_id}>
              <rect
                className={styles.bar}
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                rx="3"
                tabIndex="0"
                aria-label={tooltip(item)}
              >
                <title>{tooltip(item)}</title>
              </rect>
              <text className={styles.valueLabel} x={center} y={Math.max(y - 7, 14)} textAnchor="middle">
                {number.format(item.units_sold)}
              </text>
              <text
                className={styles.productAxisLabel}
                x={center}
                y={height - 64}
                textAnchor="end"
                transform={`rotate(-35 ${center} ${height - 64})`}
              >
                {truncate(item.product_name, 16)}
              </text>
            </g>
          );
        })}
        <text className={styles.axisLabel} x={pad.left + graphWidth / 2} y={height - 5} textAnchor="middle">
          Product Name
        </text>
        <text
          className={styles.axisLabel}
          transform={`translate(14 ${pad.top + graphHeight / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          Units Sold
        </text>
      </svg>
      <ScreenReaderData items={items} />
    </div>
  );
}

function revenueFormatter(currency, compact = false) {
  const options = currency
    ? { style: "currency", currency }
    : { maximumFractionDigits: 2 };
  return new Intl.NumberFormat("en-US", {
    ...options,
    ...(compact ? { notation: "compact" } : {}),
  });
}

function revenueTooltip(label, revenue, currency) {
  return `${label}\nRevenue: ${revenueFormatter(currency).format(revenue)}`;
}

function RevenueDimensionBars({ items, currency, dimensionLabel }) {
  const height = 320;
  const pad = { top: 28, right: 16, bottom: 88, left: 72 };
  const graphWidth = WIDTH - pad.left - pad.right;
  const graphHeight = height - pad.top - pad.bottom;
  const maximum = Math.max(1, ...items.map((item) => Number(item.revenue)));
  const usedWidth = Math.min(graphWidth, items.length * 80);
  const startX = pad.left;
  const slot = usedWidth / items.length;
  const barWidth = Math.min(42, slot * 0.64);
  const chartWidth = pad.left + usedWidth + pad.right;
  const compact = revenueFormatter(currency, true);

  return (
    <div className={styles.chartScroller}>
      <svg
        className={`${styles.chart} ${styles.dimensionChart}`}
        viewBox={`0 0 ${chartWidth} ${height}`}
        role="img"
        aria-label={`Sales revenue by ${dimensionLabel.toLowerCase()}`}
      >
        <title>Sales revenue by {dimensionLabel.toLowerCase()}</title>
        {[0, 0.5, 1].map((ratio) => {
          const y = pad.top + graphHeight * (1 - ratio);
          return (
            <g key={ratio}>
              <line
                className={styles.gridLine}
                x1={pad.left}
                x2={chartWidth - pad.right}
                y1={y}
                y2={y}
              />
              <text className={styles.axisText} x={pad.left - 8} y={y + 4} textAnchor="end">
                {compact.format(maximum * ratio)}
              </text>
            </g>
          );
        })}
        {items.map((item, index) => {
          const revenue = Number(item.revenue);
          const barHeight = (revenue / maximum) * graphHeight;
          const x = startX + index * slot + (slot - barWidth) / 2;
          const y = pad.top + graphHeight - barHeight;
          const center = x + barWidth / 2;
          const detail = revenueTooltip(item.label, revenue, currency);
          return (
            <g key={item.label}>
              <rect
                className={styles.revenueBar}
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                rx="3"
                tabIndex="0"
                aria-label={detail}
              >
                <title>{detail}</title>
              </rect>
              <text className={styles.valueLabel} x={center} y={Math.max(y - 7, 14)} textAnchor="middle">
                {compact.format(revenue)}
              </text>
              <text
                className={styles.productAxisLabel}
                x={center}
                y={height - 64}
                textAnchor="end"
                transform={`rotate(-35 ${center} ${height - 64})`}
              >
                {truncate(item.label, 16)}
              </text>
            </g>
          );
        })}
        <text className={styles.axisLabel} x={pad.left + usedWidth / 2} y={height - 5} textAnchor="middle">
          {dimensionLabel}
        </text>
        <text
          className={styles.axisLabel}
          transform={`translate(14 ${pad.top + graphHeight / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          Revenue {currency ? `(${currency})` : "(mixed currency)"}
        </text>
      </svg>
      <ul className={styles.screenReaderOnly}>
        {items.map((item) => (
          <li key={item.label}>
            {revenueTooltip(item.label, Number(item.revenue), currency)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProductRevenueBars({ items, currency }) {
  const left = 190;
  const right = 76;
  const rowHeight = 32;
  const top = 14;
  const bottom = 42;
  const height = Math.max(190, top + items.length * rowHeight + bottom);
  const graphWidth = WIDTH - left - right;
  const maximum = Math.max(1, ...items.map((item) => Number(item.revenue)));
  const compact = revenueFormatter(currency, true);

  return (
    <div className={styles.chartScroller}>
      <svg
        className={styles.chart}
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label="Product revenue contribution"
      >
        <title>Product revenue contribution</title>
        {items.map((item, index) => {
          const revenue = Number(item.revenue);
          const y = top + index * rowHeight;
          const width = (revenue / maximum) * graphWidth;
          const detail = revenueTooltip(item.product_name, revenue, currency);
          return (
            <g key={item.product_id}>
              <text className={styles.horizontalLabel} x={left - 10} y={y + 19} textAnchor="end">
                {truncate(item.product_name, 27)}
              </text>
              <rect
                className={styles.contributionBar}
                x={left}
                y={y}
                width={width}
                height="24"
                rx="3"
                tabIndex="0"
                aria-label={detail}
              >
                <title>{detail}</title>
              </rect>
              <text className={styles.horizontalValue} x={Math.min(left + width + 8, WIDTH - 64)} y={y + 18}>
                {compact.format(revenue)}
              </text>
            </g>
          );
        })}
        <text className={styles.axisLabel} x={left + graphWidth / 2} y={height - 6} textAnchor="middle">
          Revenue {currency ? `(${currency})` : "(mixed currency)"}
        </text>
      </svg>
      <ul className={styles.screenReaderOnly}>
        {items.map((item) => (
          <li key={item.product_id}>
            {revenueTooltip(item.product_name, Number(item.revenue), currency)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChartState({ message, retry, loadingLabel }) {
  return (
    <div className={styles.state}>
      {loadingLabel ? <s-spinner accessibilityLabel={loadingLabel} /> : null}
      <s-text tone={retry ? "critical" : "subdued"}>{message}</s-text>
      {retry ? <s-button onClick={retry}>Try again</s-button> : null}
    </div>
  );
}

export function ProductSalesPerformanceCharts({ filters, refreshKey = 0 }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const [salesDimension, setSalesDimension] = useState("vendor");

  useEffect(() => {
    let active = true;
    setResult(null);
    setError(null);
    fetchProductSalesPerformance(filters)
      .then((response) => active && setResult(response))
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load product sales charts.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [filters, refreshKey, requestVersion]);

  const retry = () => setRequestVersion((version) => version + 1);
  const dimensionItems =
    salesDimension === "vendor"
      ? result?.sales_by_vendor
      : result?.sales_by_product_type;
  const dimensionLabel = salesDimension === "vendor" ? "Vendor" : "Product Type";

  const content = (items, Chart, chartProps = {}) => (
    <>
      {!result && !error ? (
        <ChartState loadingLabel="Loading product sales chart" message="Loading chart..." />
      ) : null}
      {error ? <ChartState message={error} retry={retry} /> : null}
      {result && !items?.length ? (
        <ChartState message="No product sales data available for the selected period." />
      ) : null}
      {items?.length ? <Chart items={items} {...chartProps} /> : null}
    </>
  );

  return (
    <s-section heading="Product Sales Performance">
      <div className={styles.chartGrid}>
        <ChartCard title="Top Selling Products" subtitle="Top 10 products by units sold">
          {content(result?.top_selling, VerticalProductBars)}
        </ChartCard>
        <ChartCard
          title="Sales by Vendor / Product Type"
          subtitle="Which vendor or product type generates the most revenue?"
          controls={
            <label className={styles.dimensionControl}>
              <span>Group by</span>
              <select
                value={salesDimension}
                onChange={(event) => setSalesDimension(event.target.value)}
              >
                <option value="vendor">Vendor</option>
                <option value="product_type">Product Type</option>
              </select>
            </label>
          }
        >
          {content(dimensionItems, RevenueDimensionBars, {
            currency: result?.currency,
            dimensionLabel,
          })}
        </ChartCard>
        <ChartCard
          title="Product Revenue Contribution"
          subtitle="Products generating the most gross revenue"
        >
          {content(
            result?.product_revenue_contribution,
            ProductRevenueBars,
            { currency: result?.currency },
          )}
        </ChartCard>
      </div>
    </s-section>
  );
}
