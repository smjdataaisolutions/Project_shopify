const DASHBOARD_ENDPOINT = "/api/dashboard";
const BUSINESS_HIGHLIGHTS_ENDPOINT = "/api/analytics/overview/business-highlights";
const ACTION_NEEDED_ENDPOINT = "/api/analytics/overview/action-needed";
const FILTER_OPTIONS_ENDPOINT = "/api/analytics/overview/filter-options";

function withOverviewFilters(endpoint, filters = {}) {
  const params = new URLSearchParams();

  if (filters.startDate) params.set("start_date", filters.startDate);
  if (filters.endDate) params.set("end_date", filters.endDate);
  filters.orderStatuses?.forEach((status) => {
    params.append("financial_status", status);
  });
  filters.fulfillmentStatuses?.forEach((status) => {
    params.append("fulfillment_status", status);
  });
  const query = params.toString();
  return query ? `${endpoint}?${query}` : endpoint;
}

export async function fetchDashboard(filters) {
  const response = await fetch(withOverviewFilters(DASHBOARD_ENDPOINT, filters), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Dashboard request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchBusinessHighlights(filters) {
  const response = await fetch(withOverviewFilters(BUSINESS_HIGHLIGHTS_ENDPOINT, filters), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Business highlights request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchActionNeeded(filters) {
  const response = await fetch(withOverviewFilters(ACTION_NEEDED_ENDPOINT, filters), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Action needed request failed (${response.status}).`);
  }

  return response.json();
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
