import { downloadCsv } from "./download";

const INVENTORY_KPIS_ENDPOINT = "/api/analytics/inventory/kpis";
const INVENTORY_TABLE_ENDPOINT = "/api/analytics/inventory/table";

export async function fetchInventoryKpis() {
  const response = await fetch(INVENTORY_KPIS_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Inventory KPI request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchInventoryTable({
  page = 1,
  pageSize = 25,
  sortOrder = "asc",
} = {}) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_order: sortOrder,
  });
  const response = await fetch(`${INVENTORY_TABLE_ENDPOINT}?${query}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Inventory table request failed (${response.status}).`);
  }

  return response.json();
}

export async function downloadInventoryTableCsv({ sortOrder = "asc" } = {}) {
  const query = new URLSearchParams({ sort_order: sortOrder });
  await downloadCsv(
    `${INVENTORY_TABLE_ENDPOINT}/download?${query}`,
    "inventory-details.csv",
  );
}
