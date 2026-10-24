export const SALES_EXPLORER_DIMENSIONS = [
  { id: "processed_date", label: "Processed date" },
  { id: "sales_channel", label: "Sales channel" },
  { id: "product", label: "Product" },
  {
    id: "location",
    label: "Location (unavailable)",
    disabled: true,
    reason: "Orders do not currently have a verified location relationship.",
  },
];

export const SALES_EXPLORER_MEASURES = [
  { id: "revenue", label: "Revenue" },
  { id: "orders", label: "Orders" },
  { id: "units_sold", label: "Units sold" },
  { id: "average_order_value", label: "Average order value" },
];

export const SALES_EXPLORER_MATRIX = {
  processed_date: ["revenue", "orders", "units_sold", "average_order_value"],
  sales_channel: ["revenue", "orders", "units_sold", "average_order_value"],
  product: ["revenue", "orders", "units_sold"],
};

export const SALES_EXPLORER_COMPARISONS = [
  { id: "none", label: "None" },
  { id: "previous_period", label: "Previous period" },
  { id: "previous_7_days", label: "Previous 7 days" },
  { id: "previous_30_days", label: "Previous 30 days" },
];

export function explorerComparisonLabel(comparison) {
  return (
    SALES_EXPLORER_COMPARISONS.find((option) => option.id === comparison)
      ?.label || comparison
  );
}

export function formatExplorerPeriod(period) {
  if (!period) return "All time";
  const format = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  });
  const parse = (value) => new Date(`${value}T00:00:00Z`);
  return `${format.format(parse(period.start_date))}–${format.format(
    parse(period.end_date),
  )} · ${period.days} ${period.days === 1 ? "day" : "days"}`;
}

export function measuresForDimension(dimension) {
  const supported = SALES_EXPLORER_MATRIX[dimension] || [];
  return SALES_EXPLORER_MEASURES.filter((measure) =>
    supported.includes(measure.id),
  );
}

export function normalizeExplorerSelection(dimension, measure) {
  const supported = measuresForDimension(dimension);
  return supported.some((option) => option.id === measure)
    ? measure
    : supported[0]?.id || "revenue";
}

export function explorerMeasureLabel(measure) {
  return (
    SALES_EXPLORER_MEASURES.find((option) => option.id === measure)?.label ||
    measure
  );
}
