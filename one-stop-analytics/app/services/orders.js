const ORDER_KPIS_ENDPOINT = "/api/orders/kpis";
const ORDER_CHARTS_ENDPOINT = "/api/orders/charts";
const ORDER_PERFORMANCE_ENDPOINT = "/api/orders/performance-insights";

function buildOrderUrl(endpoint, filters = {}) {
  const parameters = new URLSearchParams();
  if (filters.startDate) parameters.set("start_date", filters.startDate);
  if (filters.endDate) parameters.set("end_date", filters.endDate);
  filters.salesChannels?.forEach((channel) => {
    parameters.append("sales_channel", channel);
  });
  filters.orderStatuses?.forEach((status) => {
    parameters.append("order_status", status);
  });
  filters.fulfillmentStatuses?.forEach((status) => {
    parameters.append("fulfillment_status", status);
  });
  filters.paymentStatuses?.forEach((status) => {
    parameters.append("payment_status", status);
  });
  const query = parameters.toString();
  return query ? `${endpoint}?${query}` : endpoint;
}

export function buildOrderKpisUrl(filters = {}) {
  return buildOrderUrl(ORDER_KPIS_ENDPOINT, filters);
}

export function buildOrderChartsUrl(filters = {}) {
  return buildOrderUrl(ORDER_CHARTS_ENDPOINT, filters);
}

export function buildOrderPerformanceUrl({
  filters = {},
  page = 1,
  pageSize = 10,
  search = "",
  sortBy = "order_date",
  sortDirection = "desc",
} = {}) {
  const url = new URL(buildOrderUrl(ORDER_PERFORMANCE_ENDPOINT, filters), "http://local");
  url.searchParams.set("page", page);
  url.searchParams.set("page_size", pageSize);
  if (search.trim()) url.searchParams.set("search", search.trim());
  url.searchParams.set("sort_by", sortBy);
  url.searchParams.set("sort_direction", sortDirection);
  return `${url.pathname}?${url.searchParams.toString()}`;
}

export async function fetchOrderKpis(filters) {
  const response = await fetch(buildOrderKpisUrl(filters), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Order KPI request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchOrderCharts(filters) {
  const response = await fetch(buildOrderChartsUrl(filters), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Order charts request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchOrderPerformanceInsights(options) {
  const response = await fetch(buildOrderPerformanceUrl(options), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Order performance request failed (${response.status}).`);
  }

  return response.json();
}

export function buildOrderTimelineUrl(orderId) {
  return `/api/orders/${encodeURIComponent(orderId)}/timeline`;
}

export async function fetchOrderTimeline(orderId) {
  const response = await fetch(buildOrderTimelineUrl(orderId), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Order timeline request failed (${response.status}).`);
  }

  return response.json();
}
