import { useCallback, useEffect, useRef, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { useNavigate } from "react-router";
import { ActionNeeded } from "../components/dashboard/ActionNeeded";
import { DailyStorePerformanceTable } from "../components/dashboard/DailyStorePerformanceTable";
import { KPICard } from "../components/dashboard/KPICard";
import { LastSevenDaysPerformance } from "../components/dashboard/LastSevenDaysPerformance";
import { OverviewFilters } from "../components/dashboard/OverviewFilters";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import styles from "../components/dashboard/dashboard.module.css";
import { fetchDashboard } from "../services/dashboard";
import { focusDailyPerformance } from "../utils/lastSevenDaysPerformance";
import {
  formatOverviewUpdatedAt,
  getOverviewKpiDestination,
} from "../utils/overviewNavigation";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

function getMetrics(dashboard) {
  return [
    {
      id: "total_products",
      label: "Total products",
      value: dashboard.total_products,
      definition: [
        "Definition: All synchronized Shopify products in the store.",
        "Formula: COUNT(*) from products.",
      ],
    },
    {
      id: "total_variants",
      label: "Total variants",
      value: dashboard.total_variants,
      definition: [
        "Definition: All synchronized variants belonging to store products.",
        "Formula: COUNT(*) from product_variants.",
      ],
    },
    {
      id: "low_stock_products",
      label: "Low-stock products",
      value: dashboard.low_stock_products,
      definition: [
        "Definition: Distinct products with a variant approaching stockout.",
        "Formula: COUNT(DISTINCT product_id) where inventory quantity is 1 to 10.",
      ],
    },
    {
      id: "out_of_stock_products",
      label: "Out-of-stock products",
      value: dashboard.out_of_stock_products,
      definition: [
        "Definition: Distinct products with at least one unavailable variant.",
        "Formula: COUNT(DISTINCT product_id) where inventory quantity equals 0.",
      ],
    },
    {
      id: "total_orders",
      label: "Total orders",
      value: dashboard.total_orders,
      definition: [
        "Definition: Orders matching the selected Overview filters.",
        "Formula: COUNT(*) from orders, filtered using orders.processed_at.",
      ],
    },
    {
      id: "total_revenue",
      label: "Total revenue",
      value: currencyFormatter.format(dashboard.total_revenue),
      definition: [
        "Definition: Line-item revenue from orders matching the selected filters.",
        "Formula: SUM(order_line_items.unit_price x quantity).",
      ],
    },
    {
      id: "units_sold",
      label: "Units sold",
      value: dashboard.units_sold,
      definition: [
        "Definition: Product units in matching order line items.",
        "Formula: SUM(order_line_items.quantity).",
      ],
    },
    {
      id: "average_order_value",
      label: "Average order value",
      value: currencyFormatter.format(dashboard.average_order_value),
      definition: [
        "Definition: Average line-item revenue generated per matching order.",
        "Formula: Total revenue / Total orders; returns 0 when orders equal 0.",
      ],
    },
  ];
}

export default function StorePerformanceOverview() {
  const navigate = useNavigate();
  const dailyPerformanceRef = useRef(null);
  const [areFiltersCollapsed, setAreFiltersCollapsed] = useState(false);
  const [filters, setFilters] = useState({
    startDate: "",
    endDate: "",
    orderStatuses: [],
    fulfillmentStatuses: [],
    salesChannels: [],
  });
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);

  const loadDashboard = useCallback(() => {
    setRequestVersion((version) => version + 1);
  }, []);

  const viewDailyPerformance = useCallback(() => {
    focusDailyPerformance(dailyPerformanceRef.current);
  }, []);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setDashboard(null);

    fetchDashboard(filters)
      .then((response) => {
        if (active) {
          setDashboard(response);
          setLastUpdatedAt(
            response.last_updated_at
              ? new Date(response.last_updated_at)
              : null,
          );
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message ||
              "Unable to load store performance overview.",
          );
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
    <s-page heading="Store Performance Overview" inlineSize="large">
      <AnalyticsTopNavigation>
        <s-text tone="subdued">
          Last updated: {formatOverviewUpdatedAt(lastUpdatedAt)}
        </s-text>
        <s-button
          icon="refresh"
          onClick={loadDashboard}
          disabled={isLoading}
          accessibilityLabel="Refresh Store Performance Overview"
        >
          Refresh
        </s-button>
      </AnalyticsTopNavigation>

      <div
        className={`${styles.overviewLayout} ${
          areFiltersCollapsed ? styles.overviewLayoutCollapsed : ""
        }`}
      >
        <OverviewFilters
          filters={filters}
          onChange={setFilters}
          isCollapsed={areFiltersCollapsed}
          onCollapse={() => setAreFiltersCollapsed(true)}
        />

        {areFiltersCollapsed ? (
          <aside
            className={styles.collapsedFilters}
            aria-label="Collapsed filters"
          >
            <s-button
              icon="chevron-right"
              variant="tertiary"
              accessibilityLabel="Expand filters"
              onClick={() => setAreFiltersCollapsed(false)}
            />
          </aside>
        ) : null}

        <div className={styles.overviewContent}>
          {isLoading && !dashboard ? (
            <s-section heading="Loading store performance overview">
              <s-stack direction="inline" gap="base" alignItems="center">
                <s-spinner accessibilityLabel="Loading store performance data" />
                <s-text>Retrieving your latest store metrics.</s-text>
              </s-stack>
            </s-section>
          ) : null}

          {error ? (
            <s-section heading="Unable to load store performance overview">
              <s-stack direction="block" gap="base">
                <s-text>{error}</s-text>
                <s-button onClick={loadDashboard}>Try again</s-button>
              </s-stack>
            </s-section>
          ) : null}

          {dashboard ? (
            <s-section heading="Store overview">
              <div className={styles.grid}>
                {getMetrics(dashboard).map((metric) => (
                  <KPICard
                    key={metric.id}
                    {...metric}
                    onClick={() => navigate(getOverviewKpiDestination(metric.id))}
                    accessibilityLabel={`Open ${metric.label} details`}
                  />
                ))}
              </div>
            </s-section>
          ) : null}

          <s-section heading="Last 7 Days Performance">
            <div className={styles.fixedPeriodHelper}>
              <s-text tone="subdued">
                Fixed rolling window; custom date-range selections do not apply.
              </s-text>
              <button
                type="button"
                className={styles.infoTooltip}
                title="Uses today and the previous six calendar days in the storeâ€™s time zone."
                aria-label="Uses today and the previous six calendar days in the storeâ€™s time zone."
                tabIndex="0"
              >
                â“˜
              </button>
            </div>
            <LastSevenDaysPerformance
              key={`last-seven-days:${requestVersion}`}
              filters={filters}
              onViewDailyPerformance={viewDailyPerformance}
            />
          </s-section>

          <s-section heading="Action needed">
            <ActionNeeded
              key={`action-needed:${requestVersion}`}
              filters={filters}
            />
          </s-section>

          <div
            ref={dailyPerformanceRef}
            tabIndex={-1}
            role="region"
            aria-label="Daily Store Performance"
          >
            <s-section heading="Daily Store Performance">
              <DailyStorePerformanceTable
                key={`${requestVersion}:${JSON.stringify(filters)}`}
                filters={filters}
              />
            </s-section>
          </div>
        </div>
      </div>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
