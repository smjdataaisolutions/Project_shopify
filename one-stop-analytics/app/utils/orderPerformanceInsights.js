export function getOrderPerformanceState({ isLoading, result, error, search }) {
  if (isLoading && !result) return "loading";
  if (error) return "error";
  if (!result?.items?.length) return search ? "empty_search" : "empty";
  return "ready";
}

export function getNextOrderPerformanceSort(
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

export function formatOrderDate(value, locale = "en-US") {
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

export const ORDER_PROGRESS_TONE = {
  fulfilled: "success",
  in_progress: "caution",
  open: "caution",
  cancelled: "critical",
  not_required: "neutral",
  unknown: "neutral",
};

export const FULFILLMENT_HEALTH_PRESENTATION = {
  healthy: { label: "Healthy", tone: "success" },
  attention_needed: { label: "Attention Needed", tone: "caution" },
  critical: { label: "Critical", tone: "critical" },
  cancelled: { label: "Cancelled", tone: "critical" },
  unknown: { label: "Unknown", tone: "neutral" },
};
