export const HIGHLIGHT_PRESENTATION = {
  positive: { label: "Positive", tone: "success" },
  healthy: { label: "Healthy", tone: "success" },
  stable: { label: "Stable", tone: "info" },
  moderate: { label: "Moderate", tone: "info" },
  diversified: { label: "Diversified", tone: "info" },
  high: { label: "High concentration", tone: "info" },
  new_activity: { label: "New activity", tone: "success" },
  no_activity: { label: "No activity", tone: "neutral" },
  attention: { label: "Attention", tone: "caution" },
  warning: { label: "Warning", tone: "caution" },
  critical: { label: "Critical", tone: "critical" },
  unavailable: { label: "Unavailable", tone: "neutral" },
};

export function getHighlightPresentation(status) {
  return HIGHLIGHT_PRESENTATION[status] || HIGHLIGHT_PRESENTATION.unavailable;
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

export function getHighlightDestination(highlightId) {
  if (highlightId === "product_sales_concentration") return "/app/products";
  if (highlightId === "inventory_exposure") return "/app/inventory";
  return null;
}
