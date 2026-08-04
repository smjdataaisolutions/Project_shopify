const DASHBOARD_ENDPOINT = "/api/dashboard";

export async function fetchDashboard() {
  const response = await fetch(DASHBOARD_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Dashboard request failed (${response.status}).`);
  }

  return response.json();
}
