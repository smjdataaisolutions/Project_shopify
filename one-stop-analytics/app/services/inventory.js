const INVENTORY_KPIS_ENDPOINT = "/api/analytics/inventory/kpis";

export async function fetchInventoryKpis() {
  const response = await fetch(INVENTORY_KPIS_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Inventory KPI request failed (${response.status}).`);
  }

  return response.json();
}
