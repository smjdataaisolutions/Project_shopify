import { downloadCsv } from "./download";

const INVENTORY_KPIS_ENDPOINT = "/api/analytics/inventory/kpis";
const INVENTORY_TABLE_ENDPOINT = "/api/analytics/inventory/table";
const INVENTORY_FILTER_OPTIONS_ENDPOINT =
  "/api/analytics/inventory/filter-options";

function appendInventoryFilters(query, filters = {}) {
  (filters.locationIds || []).forEach((value) =>
    query.append("location_id", value),
  );
  (filters.vendors || []).forEach((value) => query.append("vendor", value));
  (filters.inventoryStatuses || []).forEach((value) =>
    query.append("inventory_status", value),
  );
  if (filters.inventoryTracked !== null && filters.inventoryTracked != null) {
    query.set("inventory_tracked", String(filters.inventoryTracked));
  }
  return query;
}

export async function fetchInventoryFilterOptions() {
  const response = await fetch(INVENTORY_FILTER_OPTIONS_ENDPOINT, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Inventory filter request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchInventoryKpis(filters = {}) {
  const query = appendInventoryFilters(new URLSearchParams(), filters);
  const response = await fetch(`${INVENTORY_KPIS_ENDPOINT}?${query}`, {
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
  filters = {},
} = {}) {
  const query = appendInventoryFilters(
    new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      sort_order: sortOrder,
    }),
    filters,
  );
  const response = await fetch(`${INVENTORY_TABLE_ENDPOINT}?${query}`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Inventory table request failed (${response.status}).`);
  }

  return response.json();
}

export async function downloadInventoryTableCsv({
  sortOrder = "asc",
  filters = {},
} = {}) {
  const query = appendInventoryFilters(
    new URLSearchParams({ sort_order: sortOrder }),
    filters,
  );
  await downloadCsv(
    `${INVENTORY_TABLE_ENDPOINT}/download?${query}`,
    "inventory-details.csv",
  );
}
