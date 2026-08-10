import { useCallback, useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { ActionNeeded } from "../components/dashboard/ActionNeeded";
import { BusinessHighlights } from "../components/dashboard/BusinessHighlights";
import { KPICard } from "../components/dashboard/KPICard";
import { OverviewFilters } from "../components/dashboard/OverviewFilters";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import styles from "../components/dashboard/dashboard.module.css";
import { fetchDashboard } from "../services/dashboard";
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
    { label: "Total products", value: dashboard.total_products },
    { label: "Total variants", value: dashboard.total_variants },
    { label: "Low-stock products", value: dashboard.low_stock_products },
    { label: "Out-of-stock products", value: dashboard.out_of_stock_products },
    { label: "Total orders", value: dashboard.total_orders },
    {
      label: "Total revenue",
      value: currencyFormatter.format(dashboard.total_revenue),
    },
    { label: "Units sold", value: dashboard.units_sold },
    {
      label: "Average order value",
      value: currencyFormatter.format(dashboard.average_order_value),
    },
  ];
}

export default function StorePerformanceOverview() {
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

  const loadDashboard = useCallback(() => {
    setRequestVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setDashboard(null);

    fetchDashboard(filters)
      .then((response) => {
        if (active) setDashboard(response);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load store performance overview.",
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => { active = false; };
  }, [filters, requestVersion]);

  return (
    <s-page heading="Store performance overview" inlineSize="large">
      <AnalyticsTopNavigation />

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
          <aside className={styles.collapsedFilters} aria-label="Collapsed filters">
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
                  <KPICard key={metric.label} {...metric} />
                ))}
              </div>
            </s-section>
          ) : null}

          <s-section heading="Business highlights">
            <BusinessHighlights filters={filters} />
          </s-section>

          <s-section heading="Action needed">
            <ActionNeeded filters={filters} />
          </s-section>
        </div>
      </div>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
