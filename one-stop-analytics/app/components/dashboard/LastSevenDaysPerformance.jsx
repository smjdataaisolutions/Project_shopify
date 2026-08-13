/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { fetchLastSevenDaysPerformance } from "../../services/dashboard";
import {
  activateWithKeyboard,
  comparisonPresentation,
  currencyFormatter,
  formatFullDate,
  formatShortDate,
} from "../../utils/lastSevenDaysPerformance";
import styles from "./lastSevenDaysPerformance.module.css";

const CHART_WIDTH = 420;

function ChartCard({ title, children }) {
  return (
    <s-box padding="base" borderWidth="base" borderRadius="base" background="base">
      <div className={styles.card}>
        <s-heading>{title}</s-heading>
        {children}
      </div>
    </s-box>
  );
}

function LoadingCards() {
  return (
    <div className={styles.grid} aria-label="Loading Last 7 Days Performance">
      {["Orders by Day", "Top-Selling Products", "Total Revenue Comparison"].map(
        (title) => (
          <ChartCard key={title} title={title}>
            <div className={styles.loading}>
              <s-spinner accessibilityLabel={`Loading ${title}`} />
              <s-text>Loading chartâ€¦</s-text>
            </div>
          </ChartCard>
        ),
      )}
    </div>
  );
}

function ErrorCards({ message, onRetry }) {
  return (
    <div className={styles.grid}>
      {["Orders by Day", "Top-Selling Products", "Total Revenue Comparison"].map(
        (title) => (
          <ChartCard key={title} title={title}>
            <div className={styles.loading}>
              <s-text tone="critical">{message}</s-text>
              <s-button onClick={onRetry}>Try again</s-button>
            </div>
          </ChartCard>
        ),
      )}
    </div>
  );
}

function OrdersByDayChart({ data, onSelectDate }) {
  const width = CHART_WIDTH;
  const height = 230;
  const padding = { top: 12, right: 12, bottom: 42, left: 35 };
  const graphHeight = height - padding.top - padding.bottom;
  const graphWidth = width - padding.left - padding.right;
  const maximum = Math.max(...data.items.map((item) => item.orders), 1);
  const slotWidth = graphWidth / 7;
  const barWidth = Math.min(slotWidth * 0.58, 30);

  return (
    <ChartCard title="Orders by Day">
      <div className={styles.summaryMetric}>
        <strong>{data.total_orders.toLocaleString("en-US")}</strong>
        <span>Orders in the last 7 days</span>
      </div>
      {data.total_orders === 0 ? (
        <s-text tone="subdued">No orders were received in the last 7 days.</s-text>
      ) : null}
      <div className={styles.chartScroller}>
        <svg
          className={styles.chart}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Distinct orders and units sold for each of the last seven days"
        >
          <title>Orders by Day</title>
          <desc>Seven calendar dates are shown, including dates with zero orders.</desc>
          {[0, 0.5, 1].map((ratio) => {
            const y = padding.top + graphHeight * (1 - ratio);
            const tickValue = Math.round(maximum * ratio);
            return (
              <g key={ratio}>
                <line
                  className={styles.gridLine}
                  x1={padding.left}
                  x2={width - padding.right}
                  y1={y}
                  y2={y}
                />
                <text
                  className={styles.axisTick}
                  x={padding.left - 7}
                  y={y + 4}
                  textAnchor="end"
                >
                  {tickValue}
                </text>
              </g>
            );
          })}
          {data.items.map((item, index) => {
            const barHeight = (item.orders / maximum) * graphHeight;
            const x = padding.left + index * slotWidth + (slotWidth - barWidth) / 2;
            const y = padding.top + graphHeight - barHeight;
            const tooltip = `${formatFullDate(item.date)}; Orders: ${item.orders}; Units sold: ${item.units_sold}`;
            return (
              <g key={item.date}>
                <rect
                  className={styles.interactiveBar}
                  x={x}
                  y={item.orders ? y : padding.top + graphHeight - 2}
                  width={barWidth}
                  height={item.orders ? barHeight : 2}
                  rx="3"
                  tabIndex="0"
                  role="button"
                  aria-label={`${tooltip}. View daily performance.`}
                  onClick={() => onSelectDate(item.date)}
                  onKeyDown={(event) =>
                    activateWithKeyboard(event, () => onSelectDate(item.date))
                  }
                >
                  <title>{tooltip}</title>
                </rect>
                <text
                  className={styles.valueLabel}
                  x={x + barWidth / 2}
                  y={(item.orders ? y : padding.top + graphHeight - 2) - 6}
                  textAnchor="middle"
                >
                  {item.orders}
                </text>
                <text
                  className={styles.axisTick}
                  x={x + barWidth / 2}
                  y={height - 18}
                  textAnchor="middle"
                >
                  {formatShortDate(item.date)}
                </text>
              </g>
            );
          })}
          <text
            className={styles.axisLabel}
            x={padding.left + graphWidth / 2}
            y={height - 2}
            textAnchor="middle"
          >
            Date
          </text>
          <text
            className={styles.axisLabel}
            transform={`translate(11 ${padding.top + graphHeight / 2}) rotate(-90)`}
            textAnchor="middle"
          >
            Orders
          </text>
        </svg>
      </div>
      <ul className={styles.screenReaderOnly}>
        {data.items.map((item) => (
          <li key={item.date}>
            {formatFullDate(item.date)}: {item.orders} orders, {item.units_sold} units sold
          </li>
        ))}
      </ul>
    </ChartCard>
  );
}

function TopProductsChart({ data, currencyCode, onSelectProduct }) {
  const products = data.items;
  const width = CHART_WIDTH;
  const height = 230;
  const labelWidth = 142;
  const graphWidth = width - labelWidth - 48;
  const rowHeight = products.length ? 190 / products.length : 38;
  const maximum = Math.max(...products.map((product) => product.units_sold), 1);
  const money = currencyFormatter(currencyCode);
  const leader = products[0];

  return (
    <ChartCard title="Top-Selling Products">
      {leader ? (
        <div className={styles.productSummary} title={leader.product_name}>
          <span>Top product</span>
          <strong>{leader.product_name}</strong>
          <span>{leader.units_sold.toLocaleString("en-US")} units sold</span>
        </div>
      ) : (
        <s-text tone="subdued">No products were sold in the last 7 days.</s-text>
      )}
      <div className={styles.chartScroller}>
        <svg
          className={styles.chart}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Up to five products ranked by units sold in the last seven days"
        >
          <title>Top-Selling Products</title>
          <desc>Variants are combined under their Shopify product ID.</desc>
          {[0, 0.5, 1].map((ratio) => {
            const x = labelWidth + graphWidth * ratio;
            return (
              <g key={ratio}>
                <line
                  className={styles.gridLine}
                  x1={x}
                  x2={x}
                  y1="8"
                  y2="202"
                />
                <text
                  className={styles.axisTick}
                  x={x}
                  y="216"
                  textAnchor="middle"
                >
                  {Math.round(maximum * ratio)}
                </text>
              </g>
            );
          })}
          {products.map((product, index) => {
            const y = 15 + index * rowHeight;
            const barWidth = (product.units_sold / maximum) * graphWidth;
            const tooltip = `${product.product_name}; Units sold: ${product.units_sold}; Orders: ${product.orders}; Net product sales: ${money.format(product.net_product_sales)}`;
            return (
              <g key={product.product_id}>
                <text
                  className={styles.productLabel}
                  x={labelWidth - 8}
                  y={y + rowHeight * 0.5 + 4}
                  textAnchor="end"
                >
                  {product.product_name.length > 18
                    ? `${product.product_name.slice(0, 17)}â€¦`
                    : product.product_name}
                  <title>{product.product_name}</title>
                </text>
                <rect
                  className={`${styles.interactiveBar} ${styles.productBar}`}
                  x={labelWidth}
                  y={y + rowHeight * 0.15}
                  width={Math.max(barWidth, 2)}
                  height={rowHeight * 0.6}
                  rx="3"
                  tabIndex="0"
                  role="button"
                  aria-label={`${tooltip}. Open Products.`}
                  onClick={() => onSelectProduct(product.product_id)}
                  onKeyDown={(event) =>
                    activateWithKeyboard(event, () =>
                      onSelectProduct(product.product_id))
                  }
                >
                  <title>{tooltip}</title>
                </rect>
                <text
                  className={styles.valueLabel}
                  x={Math.min(labelWidth + barWidth + 6, width - 10)}
                  y={y + rowHeight * 0.5 + 4}
                  textAnchor="start"
                >
                  {product.units_sold}
                </text>
              </g>
            );
          })}
          <text
            className={styles.axisLabel}
            x={labelWidth + graphWidth / 2}
            y="229"
            textAnchor="middle"
          >
            Units sold
          </text>
          <text
            className={styles.axisLabel}
            transform="translate(10 110) rotate(-90)"
            textAnchor="middle"
          >
            Products
          </text>
        </svg>
      </div>
      <ul className={styles.screenReaderOnly}>
        {products.map((product) => (
          <li key={product.product_id}>
            {product.product_name}: {product.units_sold} units, {product.orders} orders,
            {` ${money.format(product.net_product_sales)} net product sales`}
          </li>
        ))}
      </ul>
    </ChartCard>
  );
}

function RevenueComparisonChart({ data, period, currencyCode, onSelectCurrent }) {
  const money = currencyFormatter(currencyCode);
  const presentation = comparisonPresentation(data);
  const maximum = Math.max(data.current_total_sales, data.previous_total_sales, 1);
  const bars = [
    {
      key: "current",
      label: "Current 7 days",
      amount: data.current_total_sales,
      start: period.current_start,
      end: period.current_end,
      action: onSelectCurrent,
    },
    {
      key: "previous",
      label: "Previous 7 days",
      amount: data.previous_total_sales,
      start: period.previous_start,
      end: period.previous_end,
      action: null,
    },
  ];
  const graphHeight = 145;

  return (
    <ChartCard title="Total Revenue Comparison">
      <div className={styles.summaryMetric}>
        <strong>{money.format(data.current_total_sales)}</strong>
        <s-badge tone={presentation.tone}>
          {presentation.symbol} {presentation.text}
        </s-badge>
      </div>
      {data.current_total_sales === 0 ? (
        <s-text tone="subdued">No sales were recorded in the current 7-day period.</s-text>
      ) : null}
      <div className={styles.chartScroller}>
        <svg
          className={styles.chart}
          viewBox="0 0 460 240"
          role="img"
          aria-label="Current and previous seven-day Total Revenue comparison"
        >
          <title>Total Revenue Comparison</title>
          <desc>Current and previous periods use identical non-date filters.</desc>
          {[0, 0.5, 1].map((ratio) => {
            const y = 15 + graphHeight * (1 - ratio);
            return (
              <g key={ratio}>
                <line
                  className={styles.gridLine}
                  x1="90"
                  x2="440"
                  y1={y}
                  y2={y}
                />
                <text
                  className={styles.axisTick}
                  x="84"
                  y={y + 4}
                  textAnchor="end"
                >
                  {money.format(maximum * ratio)}
                </text>
              </g>
            );
          })}
          {bars.map((bar, index) => {
            const x = 130 + index * 180;
            const barHeight = (bar.amount / maximum) * graphHeight;
            const y = 15 + graphHeight - barHeight;
            const tooltip = `${bar.label}; ${formatFullDate(bar.start)}â€“${formatFullDate(bar.end)}; Total Revenue: ${money.format(bar.amount)}`;
            return (
              <g key={bar.key}>
                <rect
                  className={bar.key === "current"
                    ? styles.interactiveBar
                    : styles.previousBar}
                  x={x}
                  y={bar.amount ? y : 158}
                  width="70"
                  height={bar.amount ? barHeight : 2}
                  rx="4"
                  tabIndex="0"
                  role={bar.action ? "button" : "img"}
                  aria-label={bar.action ? `${tooltip}. View daily performance.` : tooltip}
                  onClick={bar.action || undefined}
                  onKeyDown={bar.action
                    ? (event) => activateWithKeyboard(event, bar.action)
                    : undefined}
                >
                  <title>{tooltip}</title>
                </rect>
                <text
                  className={styles.valueLabel}
                  x={x + 35}
                  y={(bar.amount ? y : 158) - 7}
                  textAnchor="middle"
                >
                  {money.format(bar.amount)}
                </text>
                <text
                  className={styles.axisTick}
                  x={x + 35}
                  y="190"
                  textAnchor="middle"
                >
                  {bar.key === "current" ? "Current" : "Previous"}
                </text>
                <text
                  className={styles.axisTick}
                  x={x + 35}
                  y="208"
                  textAnchor="middle"
                >
                  7 days
                </text>
              </g>
            );
          })}
          <text
            className={styles.axisLabel}
            x="265"
            y="237"
            textAnchor="middle"
          >
            Period
          </text>
          <text
            className={styles.axisLabel}
            transform="translate(12 88) rotate(-90)"
            textAnchor="middle"
          >
            Total Revenue
          </text>
        </svg>
      </div>
      <p className={styles.screenReaderOnly}>
        Current period {formatFullDate(period.current_start)} through {formatFullDate(period.current_end)}:
        {` ${money.format(data.current_total_sales)}. `}
        Previous period {formatFullDate(period.previous_start)} through {formatFullDate(period.previous_end)}:
        {` ${money.format(data.previous_total_sales)}. ${presentation.text}.`}
      </p>
    </ChartCard>
  );
}

export function LastSevenDaysPerformance({ filters, onViewDailyPerformance }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const requestFilters = useMemo(
    () => ({
      orderStatuses: filters.orderStatuses,
      fulfillmentStatuses: filters.fulfillmentStatuses,
      salesChannels: filters.salesChannels,
    }),
    [filters.orderStatuses, filters.fulfillmentStatuses, filters.salesChannels],
  );

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    fetchLastSevenDaysPerformance(requestFilters)
      .then((response) => { if (active) setData(response); })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load Last 7 Days Performance.");
        }
      });
    return () => { active = false; };
  }, [requestFilters, requestVersion]);

  if (error) {
    return (
      <ErrorCards
        message={error}
        onRetry={() => setRequestVersion((version) => version + 1)}
      />
    );
  }
  if (!data) return <LoadingCards />;

  return (
    <div className={styles.grid}>
      <OrdersByDayChart
        data={data.orders_by_day}
        onSelectDate={onViewDailyPerformance}
      />
      <TopProductsChart
        data={data.top_selling_products}
        currencyCode={data.currency_code}
        onSelectProduct={() => navigate("/app/products")}
      />
      <RevenueComparisonChart
        data={data.total_revenue_comparison}
        period={data.period}
        currencyCode={data.currency_code}
        onSelectCurrent={onViewDailyPerformance}
      />
    </div>
  );
}
