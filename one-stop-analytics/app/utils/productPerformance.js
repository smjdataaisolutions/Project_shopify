export const PRODUCT_STATUS_PRESENTATION = {
  active: { label: "Active", tone: "success" },
  draft: { label: "Draft", tone: "neutral" },
  archived: { label: "Archived", tone: "neutral" },
  unknown: { label: "Unknown", tone: "neutral" },
};

export const PRODUCT_PERFORMANCE_PRESENTATION = {
  top_seller: { label: "Top Seller", tone: "success" },
  healthy: { label: "Healthy", tone: "info" },
  slow_moving: { label: "Slow Moving", tone: "caution" },
  no_sales: { label: "No Sales", tone: "neutral" },
};

export function getProductPerformanceState({ isLoading, result, error, search }) {
  if (isLoading && !result) return "loading";
  if (error) return "error";
  if (!result?.items?.length) return search ? "empty_search" : "empty";
  return "ready";
}

export function getNextProductPerformanceSort(
  sortBy,
  sortDirection,
  selectedColumn,
) {
  return {
    sortBy: selectedColumn,
    sortDirection:
      sortBy === selectedColumn && sortDirection === "desc" ? "asc" : "desc",
  };
}

export function productRevenueFormatter(currency) {
  return new Intl.NumberFormat("en-US", currency
    ? { style: "currency", currency }
    : { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
