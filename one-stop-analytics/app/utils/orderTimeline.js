export function getOrderTimelineState({ isLoading, result, error, orderId }) {
  if (isLoading) return "loading";
  if (error) return "error";
  if (result?.order_id !== orderId) return "loading";
  if (!result?.events?.length) return "empty";
  return "ready";
}

export function sortOrderTimelineEvents(events = []) {
  return [...events].sort(
    (left, right) =>
      new Date(left.occurred_at).getTime() -
      new Date(right.occurred_at).getTime(),
  );
}

export function formatTimelineDate(value, locale = "en-US") {
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(new Date(value));
}

export function formatTimelineAmount(amount, currency, locale = "en-US") {
  if (amount == null) return null;
  if (!currency) {
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  }
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
    }).format(amount);
  } catch {
    return `${Number(amount).toFixed(2)} ${currency}`;
  }
}

export function formatTimelineStatus(value) {
  if (!value) return "Unknown";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
