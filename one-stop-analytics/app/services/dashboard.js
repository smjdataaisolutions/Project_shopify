import { downloadCsv } from "./download.js";

const DASHBOARD_ENDPOINT = "/api/dashboard";
const BUSINESS_HIGHLIGHTS_ENDPOINT =
  "/api/analytics/overview/business-highlights";
const ACTION_NEEDED_ENDPOINT = "/api/analytics/overview/action-needed";
const FILTER_OPTIONS_ENDPOINT = "/api/analytics/overview/filter-options";
const DAILY_STORE_PERFORMANCE_ENDPOINT =
  "/api/analytics/store-performance/daily";
const LAST_SEVEN_DAYS_ENDPOINT =
  "/api/analytics/store-performance/last-seven-days";

function withOverviewFilters(endpoint, filters = {}, queryValues = {}) {
  const params = new URLSearchParams(queryValues);

  if (filters.startDate) params.set("start_date", filters.startDate);
  if (filters.endDate) params.set("end_date", filters.endDate);
  filters.orderStatuses?.forEach((status) => {
    params.append("financial_status", status);
  });
  filters.fulfillmentStatuses?.forEach((status) => {
    params.append("fulfillment_status", status);
  });
  filters.salesChannels?.forEach((channel) => {
    params.append("sales_channel", channel);
  });
  const query = params.toString();
  return query ? `${endpoint}?${query}` : endpoint;
}

export async function fetchDashboard(filters) {
  const response = await fetch(
    withOverviewFilters(DASHBOARD_ENDPOINT, filters),
    {
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(`Dashboard request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchBusinessHighlights(filters) {
  const response = await fetch(
    withOverviewFilters(BUSINESS_HIGHLIGHTS_ENDPOINT, filters),
    {
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(`Business highlights request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchActionNeeded(filters) {
  const response = await fetch(
    withOverviewFilters(ACTION_NEEDED_ENDPOINT, filters),
    {
      headers: { Accept: "application/json" },
    },
  );

  if (!response.ok) {
    throw new Error(`Action needed request failed (${response.status}).`);
  }

  return response.json();
}

export async function downloadActionNeededCsv({ actionId, filters }) {
  const endpoint = withOverviewFilters(
    `${ACTION_NEEDED_ENDPOINT}/${encodeURIComponent(actionId)}/download`,
    filters,
  );
  await downloadCsv(endpoint, "overview-action-needed-records.csv");
}

export async function fetchOverviewFilterOptions() {
  const response = await fetch(FILTER_OPTIONS_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Filter options request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchDailyStorePerformance({
  filters,
  page = 1,
  pageSize = 10,
  sortBy = "date",
  sortOrder = "desc",
}) {
  const endpoint = withOverviewFilters(
    DAILY_STORE_PERFORMANCE_ENDPOINT,
    filters,
    {
      page: String(page),
      page_size: String(pageSize),
      sort_by: sortBy,
      sort_order: sortOrder,
    },
  );
  const response = await fetch(endpoint, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(
      `Daily store performance request failed (${response.status}).`,
    );
  }

  return response.json();
}

export async function fetchLastSevenDaysPerformance(filters = {}) {
  const fixedWindowFilters = {
    orderStatuses: filters.orderStatuses,
    fulfillmentStatuses: filters.fulfillmentStatuses,
    salesChannels: filters.salesChannels,
  };
  const response = await fetch(
    withOverviewFilters(LAST_SEVEN_DAYS_ENDPOINT, fixedWindowFilters),
    { headers: { Accept: "application/json" } },
  );

  if (!response.ok) {
    throw new Error(`Last 7 days performance request failed (${response.status}).`);
  }
  return response.json();
}
