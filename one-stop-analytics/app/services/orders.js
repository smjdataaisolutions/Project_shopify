const ORDER_KPIS_ENDPOINT = "/api/orders/kpis";
const ORDER_CHARTS_ENDPOINT = "/api/orders/charts";

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
