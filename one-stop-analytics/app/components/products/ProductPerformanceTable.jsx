/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { fetchProductPerformance } from "../../services/products";
import {
  PRODUCT_PERFORMANCE_PRESENTATION,
  PRODUCT_STATUS_PRESENTATION,
  getNextProductPerformanceSort,
  getProductPerformanceState,
  productRevenueFormatter,
} from "../../utils/productPerformance";
import styles from "./ProductPerformanceTable.module.css";

const PAGE_SIZE = 10;
const count = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

const COLUMNS = [
  ["Product", "product"],
  ["Status", null],
  ["Units Sold", "units_sold"],
  ["Revenue", "revenue"],
  ["Orders", "orders"],
  ["Inventory", "inventory"],
  ["Sales Velocity", "sales_velocity"],
  ["Performance", "performance"],
];

function SortableHeader({ label, column, sortBy, sortDirection, onSort }) {
  if (!column) return <s-text>{label}</s-text>;
  const active = column === sortBy;
  const next = active && sortDirection === "desc" ? "ascending" : "descending";
  return (
    <div className={styles.header}>
      <s-text>{label}</s-text>
      <s-button
        variant="tertiary"
        icon={
          active
            ? sortDirection === "desc"
              ? "sort-descending"
              : "sort-ascending"
            : "sort"
        }
        accessibilityLabel={`${label}. ${active ? `Sorted ${sortDirection}. ` : ""}Sort ${next}.`}
        onClick={() => onSort(column)}
      />
    </div>
  );
}

function ProductCell({ item }) {
  return (
    <div className={styles.productCell} title={item.product_name}>
      {item.image_url ? (
        <img
          className={styles.thumbnail}
          src={item.image_url}
          alt=""
          loading="lazy"
        />
      ) : (
        <span className={styles.placeholder} aria-hidden="true">No image</span>
      )}
      <span className={styles.productName}>{item.product_name}</span>
    </div>
  );
}

export function ProductPerformanceTable({ filters, refreshKey = 0 }) {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("units_sold");
  const [sortDirection, setSortDirection] = useState("desc");
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => setPage(1), [filters]);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setResult(null);
    fetchProductPerformance({
      filters,
      page,
      pageSize: PAGE_SIZE,
      search,
      sortBy,
      sortDirection,
    })
      .then((response) => active && setResult(response))
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load product performance data.",
          );
        }
      })
      .finally(() => active && setIsLoading(false));
    return () => {
      active = false;
    };
  }, [filters, page, refreshKey, requestVersion, search, sortBy, sortDirection]);

  const revenue = useMemo(
    () => productRevenueFormatter(result?.currency),
    [result?.currency],
  );
  const state = getProductPerformanceState({ isLoading, result, error, search });

  const selectSort = (column) => {
    const next = getNextProductPerformanceSort(sortBy, sortDirection, column);
    setPage(1);
    setSortBy(next.sortBy);
    setSortDirection(next.sortDirection);
  };

  const submitSearch = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(draftSearch.trim());
  };

  return (
    <s-section heading="Product Performance Table">
      <div className={styles.container}>
        <s-text tone="subdued">
          Compare product sales, order activity, current inventory, and performance.
        </s-text>
        <form className={styles.toolbar} onSubmit={submitSearch}>
          <div className={styles.searchField}>
            <s-text-field
              label="Search products"
              value={draftSearch}
              placeholder="Product title"
              onChange={(event) => setDraftSearch(event.currentTarget.value)}
            />
          </div>
          <s-button type="submit">Search</s-button>
        </form>

        {state === "loading" ? (
          <div className={styles.state}>
            <s-spinner accessibilityLabel="Loading product performance" />
            <s-text>Retrieving product performance data.</s-text>
          </div>
        ) : null}
        {state === "error" ? (
          <div className={styles.state}>
            <s-stack direction="block" gap="base" alignItems="center">
              <s-text tone="critical">{error}</s-text>
              <s-button onClick={() => setRequestVersion((value) => value + 1)}>
                Try again
              </s-button>
            </s-stack>
          </div>
        ) : null}
        {state === "empty" ? (
          <div className={styles.state}>
            <s-text>No products found for the selected filters.</s-text>
          </div>
        ) : null}
        {state === "empty_search" ? (
          <div className={styles.state}>
            <s-text>No products found for this search.</s-text>
          </div>
        ) : null}

        {state === "ready" ? (
          <>
            {!result.currency ? (
              <s-text tone="subdued">
                Revenue contains mixed or unavailable currencies and is shown without a currency symbol.
              </s-text>
            ) : null}
            <div className={styles.tableScroll}>
              <s-table
                variant="auto"
                paginate
                loading={isLoading}
                hasPreviousPage={result.pagination.page > 1}
                hasNextPage={result.pagination.page < result.pagination.total_pages}
                onPreviousPage={() => setPage(result.pagination.page - 1)}
                onNextPage={() => setPage(result.pagination.page + 1)}
              >
                <s-table-header-row>
                  {COLUMNS.map(([label, column], index) => (
                    <s-table-header
                      key={label}
                      listSlot={index === 0 ? "primary" : "labeled"}
                      format="base"
                    >
                      <SortableHeader
                        label={label}
                        column={column}
                        sortBy={sortBy}
                        sortDirection={sortDirection}
                        onSort={selectSort}
                      />
                    </s-table-header>
                  ))}
                </s-table-header-row>
                <s-table-body>
                  {result.items.map((item) => {
                    const status = PRODUCT_STATUS_PRESENTATION[item.status] ||
                      PRODUCT_STATUS_PRESENTATION.unknown;
                    const performance =
                      PRODUCT_PERFORMANCE_PRESENTATION[item.performance];
                    return (
                      <s-table-row key={item.product_id}>
                        <s-table-cell><ProductCell item={item} /></s-table-cell>
                        <s-table-cell><s-badge tone={status.tone}>{status.label}</s-badge></s-table-cell>
                        <s-table-cell>{count.format(item.units_sold)}</s-table-cell>
                        <s-table-cell>{revenue.format(Number(item.revenue))}</s-table-cell>
                        <s-table-cell>{count.format(item.orders)}</s-table-cell>
                        <s-table-cell>{item.inventory == null ? "Unavailable" : count.format(item.inventory)}</s-table-cell>
                        <s-table-cell>{item.sales_velocity.toFixed(1)}/day</s-table-cell>
                        <s-table-cell><s-badge tone={performance.tone}>{performance.label}</s-badge></s-table-cell>
                      </s-table-row>
                    );
                  })}
                </s-table-body>
              </s-table>
            </div>
            <div className={styles.paginationSummary}>
              <s-text tone="subdued">
                Page {result.pagination.page} of {result.pagination.total_pages} · {count.format(result.pagination.total_items)} products · {result.reporting_days} reporting days
              </s-text>
            </div>
          </>
        ) : null}
      </div>
    </s-section>
  );
}
