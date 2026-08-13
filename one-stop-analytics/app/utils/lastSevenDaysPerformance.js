export function formatShortDate(value) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export function formatFullDate(value) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

export function currencyFormatter(currencyCode = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode,
  });
}

export function comparisonPresentation(comparison) {
  if (comparison.status === "new_activity") {
    return { symbol: "â†‘", text: "New sales activity", tone: "info" };
  }
  if (comparison.status === "no_change") {
    return {
      symbol: "â†’",
      text: comparison.current_total_sales === 0
        ? "No sales in either period"
        : "No change vs previous 7 days",
      tone: "neutral",
    };
  }
  const percentage = Math.abs(comparison.percentage_change || 0).toFixed(1);
  if (comparison.status === "decline") {
    return {
      symbol: "â†“",
      text: `${percentage}% vs previous 7 days`,
      tone: "critical",
    };
  }
  return {
    symbol: "â†‘",
    text: `${percentage}% vs previous 7 days`,
    tone: "success",
  };
}

export function activateWithKeyboard(event, action) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}

export function prefersReducedMotion(matchMedia) {
  const mediaMatcher = matchMedia
    || (typeof window !== "undefined" ? window.matchMedia : undefined);
  return typeof mediaMatcher === "function"
    && mediaMatcher("(prefers-reduced-motion: reduce)").matches;
}

export function focusDailyPerformance(element, matchMedia) {
  if (!element) return false;
  element.scrollIntoView({
    behavior: prefersReducedMotion(matchMedia) ? "auto" : "smooth",
    block: "start",
  });
  element.focus({ preventScroll: true });
  return true;
}
