export const OVERVIEW_KPI_DESTINATIONS = {
  total_products: "/app/products",
  total_variants: "/app/inventory?level=variant",
  low_stock_products: "/app/inventory?level=product&inventory_status=low_stock",
  out_of_stock_products:
    "/app/inventory?level=product&inventory_status=out_of_stock",
  total_orders: "/app/orders",
  total_revenue: "/app/sales",
  units_sold: "/app/sales",
  average_order_value: "/app/sales",
};

const INVENTORY_LEVELS = new Set(["product", "variant"]);
const INVENTORY_STATUSES = new Set([
  "negative",
  "out_of_stock",
  "low_stock",
  "in_stock",
  "untracked",
  "unknown",
]);

export function getOverviewKpiDestination(metricId) {
  return OVERVIEW_KPI_DESTINATIONS[metricId] || null;
}

export function getInventoryNavigationState(searchParams) {
  const requestedLevel = searchParams.get("level");
  const requestedStatuses = searchParams.getAll("inventory_status");
  return {
    level: INVENTORY_LEVELS.has(requestedLevel) ? requestedLevel : "variant",
    inventoryStatuses: requestedStatuses.filter((status) =>
      INVENTORY_STATUSES.has(status)),
  };
}

export function formatOverviewUpdatedAt(value) {
  if (!value) return "â€”";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(value);
}
