/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { fetchSalesChart } from "../../services/sales";
import {
  explorerComparisonLabel,
  explorerMeasureLabel,
  formatExplorerPeriod,
  measuresForDimension,
  normalizeExplorerSelection,
  SALES_EXPLORER_COMPARISONS,
  SALES_EXPLORER_DIMENSIONS,
} from "../../utils/salesExplorer";
import styles from "./salesExplorer.module.css";

const CHART = { width: 760, height: 320, left: 92, right: 24, top: 24, bottom: 66 };

function valueFormat(measure, currency, compact = false) {
  if (measure === "revenue" || measure === "average_order_value") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      notation: compact ? "compact" : "standard",
      maximumFractionDigits: compact ? 1 : 2,
    });
  }
  return new Intl.NumberFormat("en-US", {
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: 1,
  });
}

function shortDate(value) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(
    new Date(`${value}T00:00:00Z`),
  );
}

function measureAxisLabel(measure, currency) {
  const label = explorerMeasureLabel(measure);
  return measure === "revenue" || measure === "average_order_value"
    ? `${label} (${currency || "USD"})`
    : label;
}

function percentageChange(current, previous) {
  if (!previous) return null;
  return ((current - previous) / previous) * 100;
}

function comparisonTooltip({ label, current, previous, measure, currency, currentDate, comparisonDate, comparisonLabel }) {
  const format = valueFormat(measure, currency);
  const change = percentageChange(current, previous);
  return [
    label,
    currentDate ? `Current (${shortDate(currentDate)}): ${format.format(current)}` : `Current: ${format.format(current)}`,
    comparisonDate ? `${comparisonLabel} (${shortDate(comparisonDate)}): ${format.format(previous)}` : `${comparisonLabel}: ${format.format(previous)}`,
    change == null ? "Change: No baseline" : `Change: ${change >= 0 ? "+" : ""}${change.toFixed(1)}%`,
  ].join("\n");
}

function coordinates(data, count, maximum) {
  const graphWidth = CHART.width - CHART.left - CHART.right;
  const graphHeight = CHART.height - CHART.top - CHART.bottom;
  return data.map((point, index) => ({
    ...point,
    x: count === 1 ? CHART.left + graphWidth / 2 : CHART.left + (index / (count - 1)) * graphWidth,
    y: CHART.top + graphHeight - (point.value / maximum) * graphHeight,
  }));
}

function LineChart({ result }) {
  const { data, comparison_data: comparisonData, measure, currency } = result;
  const graphWidth = CHART.width - CHART.left - CHART.right;
  const graphHeight = CHART.height - CHART.top - CHART.bottom;
  const count = Math.max(data.length, comparisonData.length, 1);
  const maximum = Math.max(...data.map(({ value }) => value), ...comparisonData.map(({ value }) => value), 1);
  const currentPoints = coordinates(data, count, maximum);
  const previousPoints = coordinates(comparisonData, count, maximum);
  const path = (points) => points.map((point, index) => `${index ? "L" : "M"}${point.x} ${point.y}`).join(" ");
  const tickCount = Math.min(count, 5);
  const tickIndexes = [...new Set(Array.from({ length: tickCount }, (_, index) => Math.round((index * (count - 1)) / Math.max(tickCount - 1, 1))))];
  const compact = valueFormat(measure, currency, true);
  const comparisonEnabled = result.comparison !== "none";
  const comparisonLabel = explorerComparisonLabel(result.comparison);
  return (
    <svg className={styles.chart} viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="img" aria-label={`${explorerMeasureLabel(measure)} by processed date`}>
      <title>{explorerMeasureLabel(measure)} by processed date</title>
      {Array.from({ length: 5 }, (_, index) => {
        const value = (maximum / 4) * index;
        const y = CHART.top + graphHeight - (value / maximum) * graphHeight;
        return <g key={index}><line className={styles.gridLine} x1={CHART.left} x2={CHART.width - CHART.right} y1={y} y2={y} /><text className={styles.axisTick} x={CHART.left - 12} y={y + 4} textAnchor="end">{compact.format(value)}</text></g>;
      })}
      <path className={styles.line} d={path(currentPoints)} />
      {previousPoints.length ? <path className={styles.comparisonLine} d={path(previousPoints)} /> : null}
      {currentPoints.map((point, index) => {
        const previous = comparisonData[index];
        const tooltip = previous ? comparisonTooltip({ label: `Day ${index + 1}`, current: point.value, previous: previous.value, measure, currency, currentDate: point.label, comparisonDate: previous.label, comparisonLabel }) : `${point.label}: ${valueFormat(measure, currency).format(point.value)}`;
        return <g key={point.id}><circle className={styles.point} cx={point.x} cy={point.y} r="4"><title>{tooltip}</title></circle><text className={styles.dataLabel} x={point.x} y={Math.max(point.y - 10, 12)} textAnchor="middle">{compact.format(point.value)}</text></g>;
      })}
      {previousPoints.map((point, index) => {
        const tooltip = data[index] ? comparisonTooltip({ label: `Day ${index + 1}`, current: data[index].value, previous: point.value, measure, currency, currentDate: data[index].label, comparisonDate: point.label, comparisonLabel }) : `${comparisonLabel} ${point.label}: ${valueFormat(measure, currency).format(point.value)}`;
        return <g key={`comparison:${point.id}`}><circle className={styles.comparisonPoint} cx={point.x} cy={point.y} r="4"><title>{tooltip}</title></circle><text className={styles.comparisonDataLabel} x={point.x} y={Math.min(point.y + 16, CHART.top + graphHeight - 4)} textAnchor="middle">{compact.format(point.value)}</text></g>;
      })}
      {tickIndexes.map((index) => <text key={index} className={styles.axisTick} x={count === 1 ? CHART.left + graphWidth / 2 : CHART.left + (index / (count - 1)) * graphWidth} y={CHART.height - 34} textAnchor="middle">{comparisonEnabled ? `Day ${index + 1}` : shortDate(data[index].label)}</text>)}
      <text className={styles.axisLabel} x={CHART.left + graphWidth / 2} y={CHART.height - 7} textAnchor="middle">{comparisonEnabled ? "Relative day" : "Processed date"}</text>
      <text className={styles.axisLabel} transform={`translate(18 ${CHART.top + graphHeight / 2}) rotate(-90)`} textAnchor="middle">{measureAxisLabel(measure, currency)}</text>
    </svg>
  );
}

function categoryRows(data, comparisonData, currentOnly = false) {
  const previous = new Map(comparisonData.map((point) => [point.id, point]));
  const rows = data.map((point) => ({ id: point.id, label: point.label, current: point.value, previous: previous.get(point.id)?.value || 0 }));
  if (!currentOnly) {
    const currentIds = new Set(data.map(({ id }) => id));
    comparisonData.forEach((point) => {
      if (!currentIds.has(point.id)) rows.push({ id: point.id, label: point.label, current: 0, previous: point.value });
    });
  }
  return rows;
}

function VerticalBars({ result }) {
  const rows = categoryRows(result.data, result.comparison_data);
  const graphWidth = CHART.width - CHART.left - CHART.right;
  const graphHeight = CHART.height - CHART.top - CHART.bottom;
  const maximum = Math.max(...rows.flatMap(({ current, previous }) => [current, previous]), 1);
  const slot = graphWidth / rows.length;
  const grouped = result.comparison !== "none" && result.has_comparison_data;
  const barWidth = slot * (grouped ? 0.3 : 0.64);
  const compact = valueFormat(result.measure, result.currency, true);
  const comparisonLabel = explorerComparisonLabel(result.comparison);
  return (
    <svg className={styles.chart} viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="img" aria-label={`${explorerMeasureLabel(result.measure)} by sales channel`}>
      <title>{explorerMeasureLabel(result.measure)} by sales channel</title>
      {rows.map((row, index) => {
        const center = CHART.left + index * slot + slot / 2;
        const currentHeight = (row.current / maximum) * graphHeight;
        const previousHeight = (row.previous / maximum) * graphHeight;
        const tooltip = comparisonTooltip({ label: row.label, current: row.current, previous: row.previous, measure: result.measure, currency: result.currency, comparisonLabel });
        return <g key={row.id}><rect className={styles.bar} x={center - (grouped ? barWidth : barWidth / 2)} y={CHART.top + graphHeight - currentHeight} width={barWidth} height={currentHeight}><title>{grouped ? tooltip : `${row.label}: ${valueFormat(result.measure, result.currency).format(row.current)}`}</title></rect>{grouped ? <rect className={styles.comparisonBar} x={center} y={CHART.top + graphHeight - previousHeight} width={barWidth} height={previousHeight}><title>{tooltip}</title></rect> : null}<text className={styles.dataLabel} x={center - (grouped ? barWidth / 2 : 0)} y={Math.max(CHART.top + graphHeight - currentHeight - 8, 12)} textAnchor="middle">{compact.format(row.current)}</text>{grouped ? <text className={styles.comparisonDataLabel} x={center + barWidth / 2} y={Math.max(CHART.top + graphHeight - previousHeight - 8, 12)} textAnchor="middle">{compact.format(row.previous)}</text> : null}<text className={styles.axisTick} x={center} y={CHART.height - 36} textAnchor="middle">{row.label}</text></g>;
      })}
      <line className={styles.axisLine} x1={CHART.left} x2={CHART.width - CHART.right} y1={CHART.top + graphHeight} y2={CHART.top + graphHeight} />
      <text className={styles.axisLabel} x={CHART.left + graphWidth / 2} y={CHART.height - 7} textAnchor="middle">Sales channel</text>
      <text className={styles.axisLabel} transform={`translate(18 ${CHART.top + graphHeight / 2}) rotate(-90)`} textAnchor="middle">{measureAxisLabel(result.measure, result.currency)}</text>
    </svg>
  );
}

function HorizontalBars({ result }) {
  const rows = categoryRows(result.data, result.comparison_data, true);
  const width = 760;
  const left = 190;
  const right = 72;
  const grouped = result.comparison !== "none" && result.has_comparison_data;
  const rowHeight = grouped ? 68 : 48;
  const height = Math.max(180, rows.length * rowHeight + 36);
  const maximum = Math.max(...rows.flatMap(({ current, previous }) => [current, previous]), 1);
  const full = valueFormat(result.measure, result.currency);
  const comparisonLabel = explorerComparisonLabel(result.comparison);
  return (
    <svg className={styles.chart} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${explorerMeasureLabel(result.measure)} by product`}>
      <title>Current top products by {explorerMeasureLabel(result.measure).toLowerCase()}</title>
      {rows.map((row, index) => {
        const y = 12 + index * rowHeight;
        const currentWidth = (row.current / maximum) * (width - left - right);
        const previousWidth = (row.previous / maximum) * (width - left - right);
        const tooltip = comparisonTooltip({ label: row.label, current: row.current, previous: row.previous, measure: result.measure, currency: result.currency, comparisonLabel });
        return <g key={row.id}><text className={styles.productLabel} x={left - 12} y={y + (grouped ? 29 : 19)} textAnchor="end">{row.label.length > 24 ? `${row.label.slice(0, 23)}…` : row.label}</text><rect className={styles.bar} x={left} y={y} width={currentWidth} height="24" rx="3"><title>{grouped ? tooltip : `${row.label}: ${full.format(row.current)}`}</title></rect><text className={styles.barValue} x={Math.min(left + currentWidth + 8, width - right + 4)} y={y + 18}>{full.format(row.current)}</text>{grouped ? <><rect className={styles.comparisonBar} x={left} y={y + 28} width={previousWidth} height="24" rx="3"><title>{tooltip}</title></rect><text className={styles.barValue} x={Math.min(left + previousWidth + 8, width - right + 4)} y={y + 46}>{full.format(row.previous)}</text></> : null}</g>;
      })}
    </svg>
  );
}

function ChartLegend({ result }) {
  if (result.comparison === "none") return null;
  return <div className={styles.legend}><span><i className={styles.currentSwatch} />Current period</span><span><i className={styles.comparisonSwatch} />{explorerComparisonLabel(result.comparison)}</span></div>;
}

function ExplorerChart({ result }) {
  return <><ChartLegend result={result} />{result.chart_type === "line" ? <LineChart result={result} /> : result.chart_type === "horizontal_bar" ? <HorizontalBars result={result} /> : <VerticalBars result={result} />}</>;
}

function ComparisonSummary({ result }) {
  const format = valueFormat(result.measure, result.currency);
  const summary = result.summary;
  const comparisonLabel = explorerComparisonLabel(result.comparison);
  const enabled = result.comparison !== "none";
  const change = summary.percentage_change;
  return (
    <div className={styles.summary}>
      <div className={styles.summaryMetric}><span className={styles.summaryLabel}>{explorerMeasureLabel(result.measure)}</span><strong className={styles.summaryValue}>{format.format(summary.current_value)}</strong>{enabled ? <><span className={`${styles.change} ${change != null && change < 0 ? styles.negative : ""}`}>{summary.comparison_status === "no_data" ? "No data available for the comparison period." : summary.comparison_status === "no_baseline" ? "No previous-period baseline" : `${change >= 0 ? "↑" : "↓"} ${Math.abs(change).toFixed(1)}% vs ${comparisonLabel.toLowerCase()}`}</span><span className={styles.previousValue}>{comparisonLabel}: {format.format(summary.comparison_value || 0)}</span></> : null}</div>
      {result.current_period ? <div className={styles.periods}><div><span>Current period</span><strong>{formatExplorerPeriod(result.current_period)}</strong></div>{result.comparison_period ? <div><span>{comparisonLabel}</span><strong>{formatExplorerPeriod(result.comparison_period)}</strong></div> : null}</div> : null}
      {result.comparison_period && result.current_period.days !== result.comparison_period.days ? <p className={styles.durationNote}>These periods have different lengths; values shown are raw totals for each stated window.</p> : null}
    </div>
  );
}

export function SalesExplorer({ filters }) {
  const [dimension, setDimension] = useState("processed_date");
  const [measure, setMeasure] = useState("revenue");
  const [comparison, setComparison] = useState("none");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const measures = useMemo(() => measuresForDimension(dimension), [dimension]);

  useEffect(() => {
    let active = true;
    setResult(null);
    setError(null);
    fetchSalesChart({ filters, dimension, measure, comparison })
      .then((data) => active && setResult(data))
      .catch((requestError) => active && setError(requestError.message || "Unable to load Sales Explorer."));
    return () => { active = false; };
  }, [filters, dimension, measure, comparison, requestVersion]);

  const onDimensionChange = (event) => {
    const nextDimension = event.target.value;
    setDimension(nextDimension);
    setMeasure((current) => normalizeExplorerSelection(nextDimension, current));
  };

  return (
    <div className={styles.explorer}>
      <s-text tone="subdued">Customize the chart to explore your sales data.</s-text>
      <div className={styles.controls}>
        <label className={styles.field}><span>Dimension</span><select value={dimension} onChange={onDimensionChange}>{SALES_EXPLORER_DIMENSIONS.map((option) => <option key={option.id} value={option.id} disabled={option.disabled} title={option.reason}>{option.label}</option>)}</select></label>
        <label className={styles.field}><span>Measure</span><select value={measure} onChange={(event) => setMeasure(event.target.value)}>{measures.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
        <label className={styles.field}><span>Compare with</span><select value={comparison} onChange={(event) => setComparison(event.target.value)}>{SALES_EXPLORER_COMPARISONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
      </div>
      <p className={styles.dataNote}>Location is unavailable because synchronized orders have no verified location relationship.</p>
      <div className={styles.chartShell}>
        {error ? <div className={styles.state}><s-stack direction="block" gap="base" alignItems="center"><s-text tone="critical">{error}</s-text><s-button onClick={() => setRequestVersion((version) => version + 1)}>Try again</s-button></s-stack></div> : null}
        {!error && !result ? <div className={styles.state}><s-spinner accessibilityLabel="Loading Sales Explorer" /><s-text>Loading chart…</s-text></div> : null}
        {result && !result.has_current_data ? <div className={styles.state}><s-text>No sales data available for the selected period.</s-text></div> : null}
        {result?.has_current_data ? <><ComparisonSummary result={result} /><ExplorerChart result={result} /></> : null}
      </div>
    </div>
  );
}
