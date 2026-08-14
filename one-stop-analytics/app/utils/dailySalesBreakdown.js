export function getDailySalesBreakdownState({ isLoading, result, error }) {
  if (error) return "error";
  if (isLoading && !result) return "loading";
  if (!result?.items?.length) return "empty";
  return "ready";
}

export function getNextDailySalesSort(currentColumn, currentDirection, column) {
  if (currentColumn !== column) {
    return { sortBy: column, sortDirection: "desc" };
  }
  return {
    sortBy: column,
    sortDirection: currentDirection === "desc" ? "asc" : "desc",
  };
}

export function formatDailySalesDate(value, locale = "en-US") {
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}
