/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { fetchOrderPerformanceInsights } from "../../services/orders";
import { OrderTimelineModal } from "./OrderTimelineModal";
import {
  FULFILLMENT_HEALTH_PRESENTATION,
  ORDER_PROGRESS_TONE,
  formatOrderDate,
  getNextOrderPerformanceSort,
  getOrderPerformanceState,
} from "../../utils/orderPerformanceInsights";
import styles from "./orderPerformanceInsights.module.css";

const PAGE_SIZE = 10;
const countFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const COLUMNS = [
  ["Order", null],
  ["Order Date", "order_date"],
  ["Units Ordered", "units_ordered"],
  ["Order Progress", "order_progress"],
  ["Fulfillment Health", "fulfillment_health"],
  ["Timeline", null],
  ["Action", null],
];

function SortableHeader({ label, column, sortBy, sortDirection, onSort }) {
  if (!column) return <s-text>{label}</s-text>;
  const active = sortBy === column;
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
        accessibilityLabel={`${label}. ${
          active ? `Sorted ${sortDirection}. ` : ""
        }Sort ${next}.`}
        onClick={() => onSort(column)}
      />
    </div>
  );
}

export function OrderPerformanceInsights({ filters, refreshKey = 0 }) {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("order_date");
  const [sortDirection, setSortDirection] = useState("desc");
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);
  const [timelineOrder, setTimelineOrder] = useState(null);

  useEffect(() => setPage(1), [filters]);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setResult(null);

    fetchOrderPerformanceInsights({
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
            requestError.message || "Unable to load order fulfillment details.",
          );
        }
      })
      .finally(() => active && setIsLoading(false));

    return () => {
      active = false;
    };
  }, [filters, page, refreshKey, requestVersion, search, sortBy, sortDirection]);

  const selectSort = (column) => {
    const next = getNextOrderPerformanceSort(sortBy, sortDirection, column);
    setPage(1);
    setSortBy(next.sortBy);
    setSortDirection(next.sortDirection);
  };

  const submitSearch = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(draftSearch.trim());
  };

  const viewState = getOrderPerformanceState({
    isLoading,
    result,
    error,
    search,
  });

  return (
    <div className={styles.container}>
      <div className={styles.description}>
        <s-text tone="subdued">
          Track order fulfilment progress and identify orders that require attention.
        </s-text>
      </div>

      <form className={styles.toolbar} onSubmit={submitSearch}>
        <div className={styles.searchField}>
          <s-text-field
            label="Search orders"
            value={draftSearch}
            placeholder="Order number or name"
            onChange={(event) => setDraftSearch(event.currentTarget.value)}
          />
        </div>
        <s-button type="submit">Search</s-button>
      </form>

      {viewState === "loading" ? (
        <div className={styles.state}>
          <s-spinner accessibilityLabel="Loading order fulfillment details" />
          <s-text>Retrieving order fulfillment details.</s-text>
        </div>
      ) : null}

      {viewState === "error" ? (
        <div className={styles.state}>
          <s-stack direction="block" gap="base" alignItems="center">
            <s-text tone="critical">{error}</s-text>
            <s-button onClick={() => setRequestVersion((value) => value + 1)}>
              Try again
            </s-button>
          </s-stack>
        </div>
      ) : null}

      {viewState === "empty" ? (
        <div className={styles.state}>
          <s-stack direction="block" gap="small" alignItems="center">
            <s-text>No orders match the selected filters.</s-text>
            <s-text tone="subdued">
              Try changing or clearing one or more filters.
            </s-text>
          </s-stack>
        </div>
      ) : null}

      {viewState === "empty_search" ? (
        <div className={styles.state}>
          <s-text>No orders found for this search.</s-text>
        </div>
      ) : null}

      {viewState === "ready" ? (
        <>
          <div className={styles.tableScroll}>
            <s-table
              variant="auto"
              paginate
              loading={isLoading}
              hasPreviousPage={result.pagination.page > 1}
              hasNextPage={
                result.pagination.page < result.pagination.total_pages
              }
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
                  const progressTone =
                    ORDER_PROGRESS_TONE[item.order_progress] || "neutral";
                  const health =
                    FULFILLMENT_HEALTH_PRESENTATION[item.fulfillment_health] ||
                    FULFILLMENT_HEALTH_PRESENTATION.unknown;
                  return (
                    <s-table-row key={item.order_id}>
                      <s-table-cell>
                        <div className={styles.value}>{item.order_name}</div>
                      </s-table-cell>
                      <s-table-cell>
                        <div className={styles.value}>
                          {formatOrderDate(item.order_date)}
                        </div>
                      </s-table-cell>
                      <s-table-cell>
                        <div className={styles.value}>
                          {countFormatter.format(item.units_ordered)}
                        </div>
                      </s-table-cell>
                      <s-table-cell>
                        <s-badge tone={progressTone}>
                          {item.order_progress_label}
                        </s-badge>
                      </s-table-cell>
                      <s-table-cell>
                        <div
                          className={styles.health}
                          title={
                            item.fulfillment_health_reason ||
                            "No fulfillment attention conditions detected"
                          }
                        >
                          <s-badge tone={health.tone}>{health.label}</s-badge>
                        </div>
                      </s-table-cell>
                      <s-table-cell>
                        <s-button
                          accessibilityLabel={`View timeline for ${item.order_name}`}
                          onClick={() =>
                            setTimelineOrder({
                              order_id: item.order_id,
                              order_name: item.order_name,
                            })
                          }
                        >
                          View timeline
                        </s-button>
                      </s-table-cell>
                      <s-table-cell>
                        {item.shopify_admin_url ? (
                          <s-button href={item.shopify_admin_url} target="_top">
                            View order
                          </s-button>
                        ) : (
                          <s-text tone="subdued">Unavailable</s-text>
                        )}
                      </s-table-cell>
                    </s-table-row>
                  );
                })}
              </s-table-body>
            </s-table>
          </div>
          <div className={styles.paginationSummary}>
            <s-text tone="subdued">
              Page {result.pagination.page} of {result.pagination.total_pages} ·{" "}
              {countFormatter.format(result.pagination.total_items)} orders
            </s-text>
          </div>
        </>
      ) : null}
      {timelineOrder ? (
        <OrderTimelineModal
          key={timelineOrder.order_id}
          order={timelineOrder}
          onClose={() => setTimelineOrder(null)}
        />
      ) : null}
    </div>
  );
}
