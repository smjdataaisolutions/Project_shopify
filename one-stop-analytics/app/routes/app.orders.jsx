import { useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { KPICard } from "../components/dashboard/KPICard";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import {
  AppliedOrderFilters,
  hasOrderFilters,
  OrdersFilters,
} from "../components/orders/OrdersFilters";
import styles from "../components/dashboard/dashboard.module.css";
import { fetchOrderKpis } from "../services/orders";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

const countFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const percentageFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

function getMetrics(kpis) {
  return [
    {
      id: "total-orders",
      label: "Total Orders",
      value: countFormatter.format(kpis.total_orders),
      definition: [
        "Definition: Distinct orders received in the selected period.",
        "Formula: COUNT(DISTINCT orders.id) for matching processed orders.",
      ],
    },
    {
      id: "units-ordered",
      label: "Units Ordered",
      value: countFormatter.format(kpis.units_ordered),
      definition: [
        "Definition: Individual product or variant units in matching orders.",
        "Formula: SUM(order_line_items.quantity) after grouping line items by order.",
      ],
    },
    {
      id: "unfulfilled-orders",
      label: "Unfulfilled Orders",
      value: countFormatter.format(kpis.unfulfilled_orders),
      definition: [
        "Definition: Matching orders still requiring fulfillment.",
        "Formula: Count distinct orders whose normalized fulfillment status is UNFULFILLED.",
      ],
    },
    {
      id: "partially-fulfilled-orders",
      label: "Partially Fulfilled Orders",
      value: countFormatter.format(kpis.partially_fulfilled_orders),
      definition: [
        "Definition: Matching orders with only part of the order fulfilled.",
        "Formula: Count distinct orders whose normalized status is PARTIALLY_FULFILLED or PARTIAL.",
      ],
    },
    {
      id: "fulfilled-orders",
      label: "Fulfilled Orders",
      value: countFormatter.format(kpis.fulfilled_orders),
      definition: [
        "Definition: Matching orders marked completely fulfilled.",
        "Formula: Count distinct orders whose normalized fulfillment status is FULFILLED.",
      ],
    },
    {
      id: "cancelled-orders",
      label: "Cancelled Orders",
      value: countFormatter.format(kpis.cancelled_orders),
      definition: [
        "Definition: Matching orders cancelled in Shopify.",
        "Formula: COUNT(DISTINCT orders.id) where cancelled_at is populated.",
      ],
    },
    {
      id: "refunded-orders",
      label: "Refunded Orders",
      value: countFormatter.format(kpis.refunded_orders),
      definition: [
        "Definition: Distinct matching orders with refund activity.",
        "Formula: Count orders with a refund timestamp, positive refund total, or refunded financial status.",
      ],
    },
    {
      id: "fulfillment-rate",
      label: "Fulfillment Rate",
      value: `${percentageFormatter.format(kpis.fulfillment_rate)}%`,
      definition: [
        "Definition: Share of eligible non-cancelled orders that are fulfilled.",
        "Formula: Fulfilled Orders ÷ (Total Orders − Cancelled Orders) × 100.",
      ],
    },
  ];
}

export default function Orders() {
  const [areFiltersCollapsed, setAreFiltersCollapsed] = useState(false);
  const [filters, setFilters] = useState({
    startDate: "",
    endDate: "",
    salesChannels: [],
    orderStatuses: [],
    fulfillmentStatuses: [],
    paymentStatuses: [],
  });
  const [filterOptions, setFilterOptions] = useState(null);
  const [kpis, setKpis] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setKpis(null);

    fetchOrderKpis(filters)
      .then((response) => {
        if (active) setKpis(response);
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load order metrics.");
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [filters, requestVersion]);

  return (
    <s-page heading="Orders" inlineSize="large">
      <AnalyticsTopNavigation />

      {hasOrderFilters(filters) ? (
        <div className={styles.appliedSalesFilters}>
          <AppliedOrderFilters
            filters={filters}
            options={filterOptions}
            onChange={setFilters}
          />
        </div>
      ) : null}

      <div
        className={`${styles.overviewLayout} ${
          areFiltersCollapsed ? styles.overviewLayoutCollapsed : ""
        }`}
      >
        <OrdersFilters
          filters={filters}
          onChange={setFilters}
          onOptionsChange={setFilterOptions}
          isCollapsed={areFiltersCollapsed}
          onCollapse={() => setAreFiltersCollapsed(true)}
        />

        {areFiltersCollapsed ? (
          <aside
            className={styles.collapsedFilters}
            aria-label="Collapsed order filters"
          >
            <s-button
              icon="chevron-right"
              variant="tertiary"
              accessibilityLabel="Expand order filters"
              onClick={() => setAreFiltersCollapsed(false)}
            />
          </aside>
        ) : null}

        <div className={styles.overviewContent}>
          {isLoading && !kpis ? (
            <s-section heading="Loading orders">
              <s-stack direction="inline" gap="base" alignItems="center">
                <s-spinner accessibilityLabel="Loading order metrics" />
                <s-text>Retrieving your latest order metrics.</s-text>
              </s-stack>
            </s-section>
          ) : null}

          {error ? (
            <s-section heading="Unable to load orders">
              <s-stack direction="block" gap="base">
                <s-text>{error}</s-text>
                <s-button
                  onClick={() => setRequestVersion((version) => version + 1)}
                >
                  Try again
                </s-button>
              </s-stack>
            </s-section>
          ) : null}

          {kpis ? (
            <>
              {kpis.total_orders === 0 ? (
                <s-section heading="No orders found">
                  <s-text>
                    No orders match the selected filters. All order metrics are
                    shown as zero.
                  </s-text>
                </s-section>
              ) : null}
              <s-section heading="Order overview">
                <div className={`${styles.grid} ${styles.salesKpiGrid}`}>
                  {getMetrics(kpis).map((metric) => (
                    <KPICard key={metric.id} {...metric} />
                  ))}
                </div>
              </s-section>
            </>
          ) : null}
        </div>
      </div>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
