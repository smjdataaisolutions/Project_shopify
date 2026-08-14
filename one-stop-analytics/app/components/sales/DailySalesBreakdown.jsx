/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from "react";
import { fetchDailySalesBreakdown } from "../../services/sales";
import {
  formatDailySalesDate,
  getDailySalesBreakdownState,
  getNextDailySalesSort,
} from "../../utils/dailySalesBreakdown";
import styles from "./dailySalesBreakdown.module.css";

const PAGE_SIZE = 10;
const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const COLUMNS = [
  ["Date", "date", "date"],
  ["Gross sales", "gross_sales", "money"],
  ["Discounts", "discounts", "deduction"],
  ["Returns/refunds", "returns_refunds", "deduction"],
  ["Net sales", "net_sales", "money"],
  ["Shipping", "shipping", "money"],
  ["Tax", "tax", "money"],
  ["Total sales", "total_sales", "money"],
  ["Orders", "orders", "number"],
  ["Average order value", "average_order_value", "money"],
];

function SortableHeader({ label, column, sortBy, sortDirection, onSort }) {
  const active = sortBy === column;
  const next =
    active && sortDirection === "desc" ? "ascending" : "descending";
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
        accessibilityLabel={`${label}. ${
          active ? `Sorted ${sortDirection}. ` : ""
        }Sort ${next}.`}
        onClick={() => onSort(column)}
      />
    </div>
  );
}

export function DailySalesBreakdown({ filters }) {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("date");
  const [sortDirection, setSortDirection] = useState("desc");
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

    fetchDailySalesBreakdown({
      filters,
      page,
      pageSize: PAGE_SIZE,
      sortBy,
      sortDirection,
    })
      .then((response) => active && setResult(response))
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load the daily sales breakdown.",
          );
        }
      })
      .finally(() => active && setIsLoading(false));

    return () => {
      active = false;
    };
  }, [filters, page, requestVersion, sortBy, sortDirection]);

  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: result?.currency || "USD",
      }),
    [result?.currency],
  );

  const selectSort = (column) => {
    const next = getNextDailySalesSort(sortBy, sortDirection, column);
    setPage(1);
    setSortBy(next.sortBy);
    setSortDirection(next.sortDirection);
  };

  const renderValue = (record, column, type) => {
    if (type === "date") return formatDailySalesDate(record[column]);
    if (type === "number") return numberFormatter.format(record[column]);
    const formatted = currencyFormatter.format(record[column]);
    return type === "deduction" && record[column] !== 0
      ? `−${formatted}`
      : formatted;
  };

  const viewState = getDailySalesBreakdownState({ isLoading, result, error });
  if (viewState === "loading") {
    return (
      <div className={styles.state}>
        <s-spinner accessibilityLabel="Loading daily sales breakdown" />
        <s-text>Retrieving daily sales details.</s-text>
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
        <s-text>No sales data is available for the selected filters.</s-text>
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
            {COLUMNS.map(([label, column]) => (
              <s-table-header key={column} listSlot="labeled" format="base">
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
            {result.items.map((item) => (
              <s-table-row key={item.date}>
                {COLUMNS.map(([, column, type]) => (
                  <s-table-cell key={column}>
                    <div
                      className={`${styles.value} ${
                        type === "deduction" ? styles.deduction : ""
                      }`}
                    >
                      {renderValue(item, column, type)}
                    </div>
                  </s-table-cell>
                ))}
              </s-table-row>
            ))}
            <s-table-row className={styles.totalRow}>
              {COLUMNS.map(([, column, type]) => (
                <s-table-cell key={column}>
                  <div
                    className={`${styles.value} ${styles.totalValue} ${
                      type === "deduction" ? styles.deduction : ""
                    }`}
                  >
                    {column === "date"
                      ? "Total"
                      : renderValue(summary, column, type)}
                  </div>
                </s-table-cell>
              ))}
            </s-table-row>
          </s-table-body>
        </s-table>
      </div>
      <div className={styles.paginationSummary}>
        <s-text tone="subdued">
          Page {pagination.page} of {pagination.total_pages} ·{" "}
          {numberFormatter.format(pagination.total_items)} daily records
        </s-text>
      </div>
    </div>
  );
}
