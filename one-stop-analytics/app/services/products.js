const PRODUCT_KPIS_ENDPOINT = "/api/products/kpis";
const PRODUCT_SALES_PERFORMANCE_ENDPOINT = "/api/products/sales-performance";
const PRODUCT_PERFORMANCE_ENDPOINT = "/api/products/performance";

function productFilterQuery(filters = {}) {
  const parameters = new URLSearchParams();
  if (filters.startDate) parameters.set("start_date", filters.startDate);
  if (filters.endDate) parameters.set("end_date", filters.endDate);
  filters.productTypes?.forEach((value) =>
    parameters.append("product_type", value),
  );
  filters.vendors?.forEach((value) => parameters.append("vendor", value));
  filters.statuses?.forEach((value) => parameters.append("status", value));
  return parameters.toString();
}

export function buildProductKpisUrl(filters = {}) {
  const query = productFilterQuery(filters);
  return query ? `${PRODUCT_KPIS_ENDPOINT}?${query}` : PRODUCT_KPIS_ENDPOINT;
}

export function buildProductSalesPerformanceUrl(filters = {}) {
  const query = productFilterQuery(filters);
  return query
    ? `${PRODUCT_SALES_PERFORMANCE_ENDPOINT}?${query}`
    : PRODUCT_SALES_PERFORMANCE_ENDPOINT;
}

export async function fetchProductKpis(filters = {}) {
  const response = await fetch(buildProductKpisUrl(filters), {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Product KPI request failed (${response.status}).`);
  }

  return response.json();
}

export async function fetchProductSalesPerformance(filters = {}) {
  const response = await fetch(buildProductSalesPerformanceUrl(filters), {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(
      `Product sales performance request failed (${response.status}).`,
    );
  }

  return response.json();
}

export function buildProductPerformanceUrl({
  filters = {},
  page = 1,
  pageSize = 10,
  search = "",
  sortBy = "units_sold",
  sortDirection = "desc",
} = {}) {
  const parameters = new URLSearchParams(productFilterQuery(filters));
  parameters.set("page", String(page));
  parameters.set("page_size", String(pageSize));
  if (search) parameters.set("search", search);
  parameters.set("sort_by", sortBy);
  parameters.set("sort_direction", sortDirection);
  return `${PRODUCT_PERFORMANCE_ENDPOINT}?${parameters}`;
}

export async function fetchProductPerformance(options = {}) {
  const response = await fetch(buildProductPerformanceUrl(options), {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Product performance request failed (${response.status}).`);
  }

  return response.json();
}
