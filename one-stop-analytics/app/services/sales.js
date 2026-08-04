const SALES_SUMMARY_ENDPOINT = "/api/sales/summary";
const REVENUE_TREND_ENDPOINT = "/api/sales/revenue/trend";

export async function fetchSalesSummary() {
  const response = await fetch(SALES_SUMMARY_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Sales summary request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchRevenueTrend({ startDate, endDate } = {}) {
  const parameters = new URLSearchParams({ interval: "daily" });
  if (startDate) parameters.set("start_date", startDate);
  if (endDate) parameters.set("end_date", endDate);

  const response = await fetch(`${REVENUE_TREND_ENDPOINT}?${parameters}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Revenue trend request failed (${response.status}).`);
  }

  return response.json();
}
