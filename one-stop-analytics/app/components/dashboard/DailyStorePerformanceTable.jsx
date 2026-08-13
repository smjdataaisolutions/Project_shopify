/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { fetchDailyStorePerformance } from "../../services/dashboard";
import { getDailyStorePerformanceState } from "../../utils/dailyStorePerformance";
import styles from "./dailyStorePerformanceTable.module.css";

const PAGE_SIZE = 10;
const countFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

function SortableHeader({ label, column, sortBy, sortOrder, onSort }) {
  const active = sortBy === column;
  const nextOrder = active && sortOrder === "desc" ? "asc" : "desc";

  return (
    <s-stack direction="inline" gap="small" alignItems="center">
      <s-text>{label}</s-text>
      <s-button
        variant="tertiary"
        icon={
          active
            ? sortOrder === "desc"
              ? "sort-descending"
              : "sort-ascending"
            : "sort"
        }
        accessibilityLabel={`${label}. ${
          active ? `Sorted ${sortOrder}. ` : ""
        }Sort ${nextOrder}.`}
        onClick={() => onSort(column)}
      />
    </s-stack>
  );
}

function NumericCell({ children, strong = false }) {
  return (
    <div className={`${styles.tableValue} ${strong ? styles.totalValue : ""}`}>
      {children}
    </div>
  );
}

export function DailyStorePerformanceTable({ filters }) {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("date");
  const [sortOrder, setSortOrder] = useState("desc");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);

    fetchDailyStorePerformance({
      filters,
      page,
      pageSize: PAGE_SIZE,
      sortBy,
      sortOrder,
    })
      .then((response) => {
        if (active) setResult(response);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message ||
              "Unable to load daily store performance.",
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [filters, page, requestVersion, sortBy, sortOrder]);

  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: result?.currency_code || "USD",
      }),
    [result?.currency_code],
  );

  const selectSort = (column) => {
    setPage(1);
    if (column === sortBy) {
      setSortOrder((current) => (current === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(column);
      setSortOrder("desc");
    }
  };

  const viewState = getDailyStorePerformanceState({
    isLoading,
    result,
    error,
  });

  if (viewState === "loading") {
    return (
      <div className={styles.state}>
        <s-spinner accessibilityLabel="Loading daily store performance" />
        <s-text>Retrieving daily store performance.</s-text>
      </div>
    );
  }

  if (viewState === "error") {
    return (
      <div className={styles.state}>
        <s-text tone="critical">{error}</s-text>
        <s-button onClick={() => setRequestVersion((value) => value + 1)}>
          Try again
        </s-button>
      </div>
    );
  }

  if (viewState === "empty") {
    return (
      <div className={styles.state}>
        <s-text>
          No store performance data is available for the selected filters.
        </s-text>
      </div>
    );
  }

  const { pagination, summary } = result;

  return (
    <div className={styles.container}>
      <div className={styles.tableScroll}>
        <s-table
          variant="auto"
          paginate
          loading={isLoading}
          hasPreviousPage={pagination.page > 1}
          hasNextPage={pagination.page < pagination.total_pages}
          onPreviousPage={() => setPage(pagination.page - 1)}
          onNextPage={() => setPage(pagination.page + 1)}
        >
          <s-table-header-row>
            <s-table-header listSlot="primary" format="base">
              <SortableHeader
                label="Date"
                column="date"
                sortBy={sortBy}
                sortOrder={sortOrder}
                onSort={selectSort}
              />
            </s-table-header>
            <s-table-header listSlot="labeled" format="base">
              <div className={styles.tableHeader}>
                <SortableHeader
                  label="Total Revenue"
                  column="total_sales"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={selectSort}
                />
              </div>
            </s-table-header>
            <s-table-header listSlot="labeled" format="base">
              <div className={styles.tableHeader}>
                <SortableHeader
                  label="Orders"
                  column="orders"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={selectSort}
                />
              </div>
            </s-table-header>
            <s-table-header listSlot="labeled" format="base">
              <div className={styles.tableHeader}>
                <SortableHeader
                  label="Units sold"
                  column="units_sold"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={selectSort}
                />
              </div>
            </s-table-header>
            <s-table-header listSlot="labeled" format="base">
              <div className={styles.tableHeader}>
                <SortableHeader
                  label="Average order value"
                  column="average_order_value"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={selectSort}
                />
              </div>
            </s-table-header>
          </s-table-header-row>
          <s-table-body>
            {result.items.map((item) => (
              <s-table-row key={item.date}>
                <s-table-cell>
                  <div className={styles.tableValue}>
                    {new Intl.DateTimeFormat("en-US", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    }).format(new Date(`${item.date}T00:00:00`))}
                  </div>
                </s-table-cell>
                <s-table-cell>
                  <NumericCell>
                    {currencyFormatter.format(item.total_sales)}
                  </NumericCell>
                </s-table-cell>
                <s-table-cell>
                  <NumericCell>{countFormatter.format(item.orders)}</NumericCell>
                </s-table-cell>
                <s-table-cell>
                  <NumericCell>
                    {countFormatter.format(item.units_sold)}
                  </NumericCell>
                </s-table-cell>
                <s-table-cell>
                  <NumericCell>
                    {currencyFormatter.format(item.average_order_value)}
                  </NumericCell>
                </s-table-cell>
              </s-table-row>
            ))}
            <s-table-row className={styles.totalRow}>
              <s-table-cell>
                <div className={`${styles.tableValue} ${styles.totalValue}`}>
                  Total
                </div>
              </s-table-cell>
              <s-table-cell>
                <NumericCell strong>
                  {currencyFormatter.format(summary.total_sales)}
                </NumericCell>
              </s-table-cell>
              <s-table-cell>
                <NumericCell strong>
                  {countFormatter.format(summary.orders)}
                </NumericCell>
              </s-table-cell>
              <s-table-cell>
                <NumericCell strong>
                  {countFormatter.format(summary.units_sold)}
                </NumericCell>
              </s-table-cell>
              <s-table-cell>
                <NumericCell strong>
                  {currencyFormatter.format(summary.average_order_value)}
                </NumericCell>
              </s-table-cell>
            </s-table-row>
          </s-table-body>
        </s-table>
      </div>
      <div className={styles.paginationSummary}>
        <s-text tone="subdued">
          Page {pagination.page} of {pagination.total_pages} Â·{" "}
          {countFormatter.format(pagination.total_items)} daily records
        </s-text>
      </div>
    </div>
  );
}
