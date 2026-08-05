const DASHBOARD_ENDPOINT = "/api/dashboard";
const BUSINESS_HIGHLIGHTS_ENDPOINT = "/api/analytics/overview/business-highlights";

export async function fetchDashboard() {
  const response = await fetch(DASHBOARD_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Dashboard request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchBusinessHighlights() {
  const response = await fetch(BUSINESS_HIGHLIGHTS_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Business highlights request failed (${response.status}).`);
  }

  return response.json();
}
