/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { fetchOrderCharts } from "../../services/orders";
import styles from "./ordersAnalytics.module.css";

const WIDTH = 640;
const HEIGHT = 260;
const PAD = { top: 20, right: 18, bottom: 48, left: 48 };
const TITLES = [
  ["Weekly Orders Trend", "Distinct orders received by week."],
  ["Fulfillment Status", "Orders by normalized fulfillment status."],
  [
    "Orders by Sales Channel",
    "Distinct orders attributed to each sales channel.",
  ],
  [
    "Total Orders Distribution",
    "Exclusive split of fulfilled, unfulfilled, cancelled, and refunded orders.",
  ],
];
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const percentage = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
});

function dateLabel(value, granularity) {
  const date = new Date(`${value}T00:00:00Z`);
  if (granularity === "week") {
    const end = new Date(date);
    end.setUTCDate(end.getUTCDate() + 6);
    const month = new Intl.DateTimeFormat("en-US", {
      month: "short",
      timeZone: "UTC",
    });
    const startMonth = month.format(date);
    const endMonth = month.format(end);
    return startMonth === endMonth
      ? `${startMonth} ${date.getUTCDate()}-${end.getUTCDate()}`
      : `${startMonth} ${date.getUTCDate()}-${endMonth} ${end.getUTCDate()}`;
  }
  if (granularity === "month") {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(date);
  }
  const formatted = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
  return formatted;
}

function Card({ title, subtitle, children }) {
  return (
    <s-box
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <article className={styles.card} aria-label={title}>
        <div>
          <s-heading>{title}</s-heading>
          <s-text tone="subdued">{subtitle}</s-text>
        </div>
        {children}
      </article>
    </s-box>
  );
}

function Grid({ children, label = "Orders analytics charts" }) {
  return (
    <div className={styles.grid} aria-label={label}>
      {children}
    </div>
  );
}

function LoadingCards() {
  return (
    <Grid label="Loading orders analytics">
      {TITLES.map(([title, subtitle]) => (
        <Card key={title} title={title} subtitle={subtitle}>
          <div className={styles.state}>
            <s-spinner accessibilityLabel={`Loading ${title}`} />
            <s-text>Loading chart…</s-text>
          </div>
        </Card>
      ))}
    </Grid>
  );
}

function StateCards({ message, retry }) {
  return (
    <Grid>
      {TITLES.map(([title, subtitle]) => (
        <Card key={title} title={title} subtitle={subtitle}>
          <div className={styles.state}>
            <s-text tone={retry ? "critical" : "subdued"}>{message}</s-text>
            {retry ? <s-button onClick={retry}>Try again</s-button> : null}
          </div>
        </Card>
      ))}
    </Grid>
  );
}

function ticks(maximum) {
  return [0, 0.5, 1].map((ratio) => ({
    ratio,
    value: Math.round(maximum * ratio),
  }));
}

function LineChart({ title, items, granularity, series, showValues = false }) {
  const graphW = WIDTH - PAD.left - PAD.right;
  const graphH = HEIGHT - PAD.top - PAD.bottom;
  const maximum = Math.max(
    1,
    ...items.flatMap((item) => series.map((entry) => item[entry.key])),
  );
  const point = (item, index, entry) => ({
    x:
      PAD.left +
      (items.length === 1 ? graphW / 2 : (index * graphW) / (items.length - 1)),
    y: PAD.top + graphH - (item[entry.key] / maximum) * graphH,
  });
  const labelStep = Math.max(1, Math.ceil(items.length / 6));
  return (
    <div className={styles.chartScroller}>
      <svg
        className={styles.chart}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={title}
      >
        <title>{title}</title>
        {ticks(maximum).map(({ ratio, value }) => {
          const y = PAD.top + graphH * (1 - ratio);
          return (
            <g key={ratio}>
              <line
                className={styles.gridLine}
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y}
                y2={y}
              />
              <text
                className={styles.axisText}
                x={PAD.left - 8}
                y={y + 4}
                textAnchor="end"
              >
                {number.format(value)}
              </text>
            </g>
          );
        })}
        {series.map((entry) => {
          const points = items.map((item, index) => point(item, index, entry));
          return (
            <g key={entry.key}>
              <polyline
                className={`${styles.line} ${styles[entry.className]}`}
                points={points.map(({ x, y }) => `${x},${y}`).join(" ")}
              />
              {points.map(({ x, y }, index) => (
                <g key={items[index].date}>
                  <circle
                    className={`${styles.point} ${styles[entry.className]}`}
                    cx={x}
                    cy={y}
                    r="4"
                    tabIndex="0"
                    aria-label={`${dateLabel(items[index].date, granularity)}; ${entry.label}: ${number.format(items[index][entry.key])}`}
                  >
                    <title>
                      {dateLabel(items[index].date, granularity)} —{" "}
                      {entry.label}: {number.format(items[index][entry.key])}
                    </title>
                  </circle>
                  {showValues ? (
                    <text
                      className={styles.valueText}
                      x={x}
                      y={Math.max(PAD.top + 10, y - 9)}
                      textAnchor="middle"
                      aria-hidden="true"
                    >
                      {number.format(items[index][entry.key])}
                    </text>
                  ) : null}
                </g>
              ))}
            </g>
          );
        })}
        {items.map((item, index) =>
          index % labelStep === 0 || index === items.length - 1 ? (
            <text
              key={item.date}
              className={styles.axisText}
              x={point(item, index, series[0]).x}
              y={HEIGHT - 20}
              textAnchor="middle"
            >
              {dateLabel(item.date, granularity)}
            </text>
          ) : null,
        )}
        <text
          className={styles.axisLabel}
          x={PAD.left + graphW / 2}
          y={HEIGHT - 3}
          textAnchor="middle"
        >
          Week
        </text>
        <text
          className={styles.axisLabel}
          transform={`translate(13 ${PAD.top + graphH / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          Orders
        </text>
      </svg>
      <ul className={styles.screenReaderOnly}>
        {items.map((item) => (
          <li key={item.date}>
            {dateLabel(item.date, granularity)}:{" "}
            {series
              .map(
                (entry) => `${entry.label} ${number.format(item[entry.key])}`,
              )
              .join(", ")}
          </li>
        ))}
      </ul>
    </div>
  );
}

function VerticalBars({ items }) {
  const graphW = WIDTH - PAD.left - PAD.right,
    graphH = HEIGHT - PAD.top - PAD.bottom;
  const maximum = Math.max(1, ...items.map((item) => item.orders));
  const slot = graphW / items.length,
    barW = Math.min(100, slot * 0.56);
  return (
    <div className={styles.chartScroller}>
      <svg
        className={styles.chart}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Orders by fulfillment status"
      >
        <title>Fulfillment Status</title>
        {ticks(maximum).map(({ ratio, value }) => {
          const y = PAD.top + graphH * (1 - ratio);
          return (
            <g key={ratio}>
              <line
                className={styles.gridLine}
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={y}
                y2={y}
              />
              <text
                className={styles.axisText}
                x={PAD.left - 8}
                y={y + 4}
                textAnchor="end"
              >
                {value}
              </text>
            </g>
          );
        })}
        {items.map((item, index) => {
          const height = (item.orders / maximum) * graphH,
            x = PAD.left + index * slot + (slot - barW) / 2,
            y = PAD.top + graphH - height;
          return (
            <g key={item.status}>
              <rect
                className={styles.bar}
                x={x}
                y={item.orders ? y : PAD.top + graphH - 2}
                width={barW}
                height={item.orders ? height : 2}
                rx="4"
                tabIndex="0"
                aria-label={`${item.status}: ${number.format(item.orders)} orders`}
              >
                <title>
                  {item.status}: {number.format(item.orders)} orders
                </title>
              </rect>
              <text
                className={styles.valueText}
                x={x + barW / 2}
                y={(item.orders ? y : PAD.top + graphH - 2) - 6}
                textAnchor="middle"
              >
                {number.format(item.orders)}
              </text>
              <text
                className={styles.axisText}
                x={x + barW / 2}
                y={HEIGHT - 20}
                textAnchor="middle"
              >
                {item.status}
              </text>
            </g>
          );
        })}
        <text
          className={styles.axisLabel}
          x={PAD.left + graphW / 2}
          y={HEIGHT - 3}
          textAnchor="middle"
        >
          Fulfillment status
        </text>
      </svg>
    </div>
  );
}

function HorizontalBars({ items }) {
  const shown = items.slice(0, 8),
    labelW = 160,
    graphW = WIDTH - labelW - 55,
    rowH = shown.length ? 205 / shown.length : 30,
    maximum = Math.max(1, ...shown.map((item) => item.orders));
  return (
    <div className={styles.chartScroller}>
      <svg
        className={styles.chart}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Orders by sales channel"
      >
        <title>Orders by Sales Channel</title>
        {shown.map((item, index) => {
          const y = 10 + index * rowH,
            width = (item.orders / maximum) * graphW;
          return (
            <g key={item.sales_channel}>
              <text
                className={styles.channelText}
                x={labelW - 8}
                y={y + rowH * 0.58}
                textAnchor="end"
              >
                {item.sales_channel.length > 20
                  ? `${item.sales_channel.slice(0, 19)}…`
                  : item.sales_channel}
                <title>{item.sales_channel}</title>
              </text>
              <rect
                className={styles.channelBar}
                x={labelW}
                y={y + rowH * 0.18}
                width={Math.max(2, width)}
                height={rowH * 0.58}
                rx="3"
                tabIndex="0"
                aria-label={`${item.sales_channel}: ${number.format(item.orders)} orders`}
              >
                <title>
                  {item.sales_channel}: {number.format(item.orders)} orders
                </title>
              </rect>
              <text
                className={styles.valueText}
                x={Math.min(labelW + width + 7, WIDTH - 25)}
                y={y + rowH * 0.58}
                textAnchor="start"
              >
                {number.format(item.orders)}
              </text>
            </g>
          );
        })}
        <text
          className={styles.axisLabel}
          x={labelW + graphW / 2}
          y={HEIGHT - 3}
          textAnchor="middle"
        >
          Orders
        </text>
      </svg>
    </div>
  );
}

function piePoint(centerX, centerY, radius, angle) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: centerX + radius * Math.cos(radians),
    y: centerY + radius * Math.sin(radians),
  };
}

function piePath(centerX, centerY, radius, startAngle, endAngle) {
  const start = piePoint(centerX, centerY, radius, startAngle);
  const end = piePoint(centerX, centerY, radius, endAngle);
  return [
    `M ${centerX} ${centerY}`,
    `L ${start.x} ${start.y}`,
    `A ${radius} ${radius} 0 ${endAngle - startAngle > 180 ? 1 : 0} 1 ${end.x} ${end.y}`,
    "Z",
  ].join(" ");
}

function OrderStatusPie({ items }) {
  const classNames = {
    Fulfilled: "pieFulfilled",
    Unfulfilled: "pieUnfulfilled",
    Cancelled: "pieCancelled",
    Refunded: "pieRefunded",
  };
  const slices = items.map((item) => ({
    label: item.status,
    value: item.orders,
    className: classNames[item.status],
  }));
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);

  if (total === 0) {
    return (
      <div className={styles.state}>
        <s-text tone="subdued">No orders match the selected filters.</s-text>
      </div>
    );
  }

  let angle = 0;
  return (
    <div className={styles.pieLayout}>
      <svg
        className={styles.pieChart}
        viewBox="0 0 520 340"
        role="img"
        aria-label="Percentage distribution of total orders by exclusive order status"
      >
        <title>Total Orders Distribution</title>
        {slices.map((slice) => {
          const startAngle = angle;
          const sliceAngle = (slice.value / total) * 360;
          const endAngle = startAngle + sliceAngle;
          const middle = startAngle + sliceAngle / 2;
          const lineStart = piePoint(260, 160, 123, middle);
          const lineEnd = piePoint(260, 160, 143, middle);
          const labelPoint = piePoint(260, 160, 155, middle);
          const insidePoint = piePoint(260, 160, 73, middle);
          const textAnchor = labelPoint.x < 260 ? "end" : "start";
          const share = (slice.value / total) * 100;
          angle = endAngle;
          return (
            <g key={slice.label}>
              {sliceAngle >= 359.999 ? (
                <circle
                  className={styles[slice.className]}
                  cx="260"
                  cy="160"
                  r="120"
                  tabIndex="0"
                  aria-label={`${slice.label}: ${number.format(slice.value)}, ${percentage.format(share)} percent of total orders`}
                >
                  <title>
                    {slice.label}: {number.format(slice.value)} (
                    {percentage.format(share)}%)
                  </title>
                </circle>
              ) : (
                <path
                  className={styles[slice.className]}
                  d={piePath(260, 160, 120, startAngle, endAngle)}
                  tabIndex="0"
                  aria-label={`${slice.label}: ${number.format(slice.value)}, ${percentage.format(share)} percent of total orders`}
                >
                  <title>
                    {slice.label}: {number.format(slice.value)} (
                    {percentage.format(share)}%)
                  </title>
                </path>
              )}
              {slice.value > 0 ? (
                <>
                  <line
                    className={styles.pieLeader}
                    x1={lineStart.x}
                    y1={lineStart.y}
                    x2={lineEnd.x}
                    y2={lineEnd.y}
                    aria-hidden="true"
                  />
                  <text
                    className={styles.pieExternalLabel}
                    x={labelPoint.x + (textAnchor === "start" ? 4 : -4)}
                    y={labelPoint.y + 4}
                    textAnchor={textAnchor}
                    aria-hidden="true"
                  >
                    {slice.label}: {number.format(slice.value)}
                  </text>
                  <text
                    className={styles.pieValue}
                    x={insidePoint.x}
                    y={insidePoint.y + 4}
                    textAnchor="middle"
                    aria-hidden="true"
                  >
                    {percentage.format(share)}%
                  </text>
                </>
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ReadyCharts({ data }) {
  return (
    <Grid>
      <Card title={TITLES[0][0]} subtitle={TITLES[0][1]}>
        <LineChart
          title="Weekly Orders Trend"
          items={data.orders_trend}
          granularity={data.granularity}
          series={[{ key: "orders", label: "Orders", className: "ordersLine" }]}
          showValues
        />
      </Card>
      <Card title={TITLES[1][0]} subtitle={TITLES[1][1]}>
        <VerticalBars items={data.fulfillment_status} />
      </Card>
      <Card title={TITLES[2][0]} subtitle={TITLES[2][1]}>
        <HorizontalBars items={data.orders_by_sales_channel} />
      </Card>
      <Card title={TITLES[3][0]} subtitle={TITLES[3][1]}>
        <OrderStatusPie items={data.order_status_distribution} />
      </Card>
    </Grid>
  );
}

export function OrdersAnalytics({ filters, refreshKey }) {
  const [data, setData] = useState(null),
    [error, setError] = useState(null),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    fetchOrderCharts(filters)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((reason) => {
        if (active) setError(reason.message || "Unable to load order charts.");
      });
    return () => {
      active = false;
    };
  }, [filters, refreshKey, retry]);
  if (error)
    return (
      <StateCards
        message={error}
        retry={() => setRetry((value) => value + 1)}
      />
    );
  if (!data) return <LoadingCards />;
  if (!data.orders_trend.some((item) => item.orders > 0))
    return <StateCards message="No chart data matches the selected filters." />;
  return <ReadyCharts data={data} />;
}
