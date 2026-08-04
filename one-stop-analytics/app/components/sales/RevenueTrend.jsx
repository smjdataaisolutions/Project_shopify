/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { fetchRevenueTrend } from "../../services/sales";
import styles from "./revenueTrend.module.css";

function RevenueChart({ points, currency }) {
  const currencyCode = currency || "USD";
  const fullCurrencyFormatter = useMemo(() => new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode,
  }), [currencyCode]);
  const compactCurrencyFormatter = useMemo(() => new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode,
    notation: "compact",
    maximumFractionDigits: 1,
  }), [currencyCode]);

  const { line, area, coordinates, xTicks, yTicks, chart } = useMemo(() => {
    const width = 700;
    const height = 300;
    const padding = { top: 18, right: 20, bottom: 58, left: 82 };
    const graphWidth = width - padding.left - padding.right;
    const graphHeight = height - padding.top - padding.bottom;
    const maximum = Math.max(...points.map((point) => point.revenue), 1);
    const pointCoordinates = points.map((point, index) => {
      const x = points.length === 1
        ? padding.left + (graphWidth / 2)
        : padding.left + (index / (points.length - 1)) * graphWidth;
      const y = padding.top + graphHeight - (point.revenue / maximum) * graphHeight;
      return { ...point, x, y };
    });
    const linePath = pointCoordinates.map(({ x, y }, index) => `${index ? "L" : "M"}${x} ${y}`).join(" ");
    const areaPath = `${linePath} L ${pointCoordinates.at(-1).x} ${height - padding.bottom} L ${pointCoordinates[0].x} ${height - padding.bottom} Z`;
    const dateLabel = (value) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(`${value}T00:00:00`));
    const xTickCount = Math.min(points.length, 5);
    const tickIndexes = xTickCount === 1
      ? [0]
      : Array.from({ length: xTickCount }, (_, index) => Math.round((index * (points.length - 1)) / (xTickCount - 1)));

    return {
      line: linePath,
      area: areaPath,
      coordinates: pointCoordinates,
      xTicks: [...new Set(tickIndexes)].map((index) => ({
        text: dateLabel(points[index].date),
        x: pointCoordinates[index].x,
      })),
      yTicks: Array.from({ length: 5 }, (_, index) => {
        const value = (maximum / 4) * index;
        return {
          value,
          y: padding.top + graphHeight - (value / maximum) * graphHeight,
        };
      }),
      chart: { width, height, padding, graphHeight },
    };
  }, [points]);

  return (
    <div className={styles.chartWrap}>
      <div className={styles.chartHeader}>
        <s-stack direction="inline" gap="small" alignItems="center">
          <span className={styles.legendSwatch} aria-hidden="true" />
          <s-text>Revenue ({currencyCode})</s-text>
          <s-badge>Daily</s-badge>
        </s-stack>
      </div>
      <svg className={styles.chart} viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={`Daily revenue trend in ${currencyCode}`}>
        <title>Daily revenue trend</title>
        <desc>Revenue grouped by the date each Shopify order was processed.</desc>
        {yTicks.map((tick) => (
          <g key={tick.value}>
            <line
              className={styles.gridLine}
              x1={chart.padding.left}
              x2={chart.width - chart.padding.right}
              y1={tick.y}
              y2={tick.y}
            />
            <text className={styles.axisTick} x={chart.padding.left - 12} y={tick.y + 4} textAnchor="end">
              {compactCurrencyFormatter.format(tick.value)}
            </text>
          </g>
        ))}
        <path className={styles.area} d={area} />
        <path className={styles.line} d={line} />
        {coordinates.map((point) => (
          <circle key={point.date} className={styles.point} cx={point.x} cy={point.y} r="4">
            <title>{`${point.date}: ${fullCurrencyFormatter.format(point.revenue)}`}</title>
          </circle>
        ))}
        {xTicks.map((tick) => (
          <text key={`${tick.text}-${tick.x}`} x={tick.x} y={chart.height - 31} textAnchor="middle" className={styles.axisTick}>
            {tick.text}
          </text>
        ))}
        <text className={styles.axisLabel} x={chart.padding.left + ((chart.width - chart.padding.left - chart.padding.right) / 2)} y={chart.height - 5} textAnchor="middle">
          Processed date
        </text>
        <text className={styles.axisLabel} transform={`translate(18 ${chart.padding.top + (chart.graphHeight / 2)}) rotate(-90)`} textAnchor="middle">
          Revenue ({currencyCode})
        </text>
      </svg>
    </div>
  );
}

export function RevenueTrend() {
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setTrend(null);
    setError(null);
    fetchRevenueTrend()
      .then((data) => active && setTrend(data))
      .catch((requestError) => active && setError(requestError.message || "Unable to load revenue trend."));
    return () => { active = false; };
  }, [requestVersion]);

  const retry = () => setRequestVersion((version) => version + 1);

  const content = (() => {
    if (error) {
      return (
        <div className={styles.empty}>
          <s-stack direction="block" gap="base" alignItems="center">
            <s-text tone="critical">{error}</s-text>
            <s-button onClick={retry}>Try again</s-button>
          </s-stack>
        </div>
      );
    }
    if (!trend) return <div className={styles.loading}><s-spinner accessibilityLabel="Loading revenue trend" /><s-text>Loading revenue trend…</s-text></div>;
    if (!trend.data.length) return <div className={styles.empty}><s-text>No revenue data is available for this date range.</s-text></div>;
    return <RevenueChart points={trend.data} currency={trend.currency} />;
  })();

  return content;
}
