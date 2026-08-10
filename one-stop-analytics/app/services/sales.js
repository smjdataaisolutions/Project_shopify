const SALES_SUMMARY_ENDPOINT = "/api/sales/summary";
const REVENUE_TREND_ENDPOINT = "/api/sales/revenue/trend";
const SALES_ACTION_NEEDED_ENDPOINT = "/api/sales/action-needed";

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

export async function fetchSalesActionNeeded({ startDate, endDate } = {}) {
  const parameters = new URLSearchParams();
  if (startDate) parameters.set("start_date", startDate);
  if (endDate) parameters.set("end_date", endDate);
  const query = parameters.toString();
  const endpoint = query
    ? `${SALES_ACTION_NEEDED_ENDPOINT}?${query}`
    : SALES_ACTION_NEEDED_ENDPOINT;

  const response = await fetch(endpoint, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Sales action needed request failed (${response.status}).`);
  }

  return response.json();
}

export async function downloadSalesActionNeededCsv({
  actionId,
  startDate,
  endDate,
}) {
  const parameters = new URLSearchParams();
  if (startDate) parameters.set("start_date", startDate);
  if (endDate) parameters.set("end_date", endDate);
  const query = parameters.toString();
  const endpoint = `/api/sales/action-needed/${encodeURIComponent(actionId)}/download${
    query ? `?${query}` : ""
  }`;

  const response = await fetch(endpoint, {
    headers: { Accept: "text/csv" },
  });
  if (!response.ok) {
    throw new Error(`CSV download request failed (${response.status}).`);
  }

  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = filenameMatch?.[1] || "sales-action-needed-records.csv";
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
