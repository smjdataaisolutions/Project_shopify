const ORDER_KPIS_ENDPOINT = "/api/orders/kpis";

export function buildOrderKpisUrl(filters = {}) {
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
  return query ? `${ORDER_KPIS_ENDPOINT}?${query}` : ORDER_KPIS_ENDPOINT;
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
