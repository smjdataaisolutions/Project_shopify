import { useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { KPICard } from "../components/dashboard/KPICard";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import { RevenueTrend } from "../components/sales/RevenueTrend";
import { SalesActionNeeded } from "../components/sales/SalesActionNeeded";
import { SalesFilters } from "../components/sales/SalesFilters";
import styles from "../components/dashboard/dashboard.module.css";
import { fetchSalesSummary } from "../services/sales";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

function getMetrics(summary) {
  const currencyFormatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: summary.currency || "USD",
  });
  return [
    {
      label: "Gross sales",
      value: currencyFormatter.format(summary.gross_sales),
    },
    { label: "Discounts", value: currencyFormatter.format(summary.discounts) },
    { label: "Net sales", value: currencyFormatter.format(summary.net_sales) },
    { label: "Shipping", value: currencyFormatter.format(summary.shipping) },
    { label: "Taxes", value: currencyFormatter.format(summary.taxes) },
    {
      label: "Total sales",
      value: currencyFormatter.format(summary.total_sales),
    },
    { label: "Orders", value: summary.orders_count },
    {
      label: "Average order value",
      value: currencyFormatter.format(summary.average_order_value),
    },
  ];
}

export default function Sales() {
  const [areFiltersCollapsed, setAreFiltersCollapsed] = useState(false);
  const [filters, setFilters] = useState({
    startDate: "",
    endDate: "",
    salesChannels: [],
    orderStatuses: [],
    currencies: [],
  });
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setSummary(null);

    fetchSalesSummary(filters)
      .then((response) => {
        if (active) setSummary(response);
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load the sales summary.");
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
    <s-page heading="Sales" inlineSize="large">
      <AnalyticsTopNavigation />

      <div
        className={`${styles.overviewLayout} ${
          areFiltersCollapsed ? styles.overviewLayoutCollapsed : ""
        }`}
      >
        <SalesFilters
          filters={filters}
          onChange={setFilters}
          isCollapsed={areFiltersCollapsed}
          onCollapse={() => setAreFiltersCollapsed(true)}
        />

        {areFiltersCollapsed ? (
          <aside
            className={styles.collapsedFilters}
            aria-label="Collapsed sales filters"
          >
            <s-button
              icon="chevron-right"
              variant="tertiary"
              accessibilityLabel="Expand sales filters"
              onClick={() => setAreFiltersCollapsed(false)}
            />
          </aside>
        ) : null}

        <div className={styles.overviewContent}>
          {isLoading && !summary ? (
            <s-section heading="Loading sales">
              <s-stack direction="inline" gap="base" alignItems="center">
                <s-spinner accessibilityLabel="Loading sales data" />
                <s-text>Retrieving your latest sales metrics.</s-text>
              </s-stack>
            </s-section>
          ) : null}

          {error ? (
            <s-section heading="Unable to load sales">
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

          {summary ? (
            <s-section heading="Sales overview">
              <div className={styles.grid}>
                {getMetrics(summary).map((metric) => (
                  <KPICard key={metric.label} {...metric} />
                ))}
              </div>
            </s-section>
          ) : null}

          <s-section heading="Revenue trend">
            <RevenueTrend filters={filters} />
          </s-section>

          <s-section heading="Action needed">
            <SalesActionNeeded filters={filters} />
          </s-section>
        </div>
      </div>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
