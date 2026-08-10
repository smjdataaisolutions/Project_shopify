const SALES_SUMMARY_ENDPOINT = "/api/sales/summary";
const REVENUE_TREND_ENDPOINT = "/api/sales/revenue/trend";
const SALES_ACTION_NEEDED_ENDPOINT = "/api/sales/action-needed";
const SALES_FILTER_OPTIONS_ENDPOINT = "/api/sales/filter-options";

function withSalesFilters(endpoint, filters = {}, extraParameters = {}) {
  const parameters = new URLSearchParams(extraParameters);
  if (filters.startDate) parameters.set("start_date", filters.startDate);
  if (filters.endDate) parameters.set("end_date", filters.endDate);
  filters.salesChannels?.forEach((channel) => {
    parameters.append("sales_channel", channel);
  });
  filters.orderStatuses?.forEach((status) => {
    parameters.append("financial_status", status);
  });
  filters.currencies?.forEach((currency) => {
    parameters.append("currency", currency);
  });
  const query = parameters.toString();
  return query ? `${endpoint}?${query}` : endpoint;
}

export async function fetchSalesSummary(filters) {
  const response = await fetch(
    withSalesFilters(SALES_SUMMARY_ENDPOINT, filters),
    {
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(`Sales summary request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchSalesFilterOptions() {
  const response = await fetch(SALES_FILTER_OPTIONS_ENDPOINT, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `Sales filter options request failed (${response.status}).`,
    );
  }
  return response.json();
}

export async function fetchRevenueTrend(filters) {
  const response = await fetch(
    withSalesFilters(REVENUE_TREND_ENDPOINT, filters, { interval: "daily" }),
    {
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(`Revenue trend request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchSalesActionNeeded(filters) {
  const response = await fetch(
    withSalesFilters(SALES_ACTION_NEEDED_ENDPOINT, filters),
    {
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(`Sales action needed request failed (${response.status}).`);
  }

  return response.json();
}

export async function downloadSalesActionNeededCsv({ actionId, filters }) {
  const endpoint = withSalesFilters(
    `/api/sales/action-needed/${encodeURIComponent(actionId)}/download`,
    filters,
  );

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
