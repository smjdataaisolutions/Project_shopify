import { useCallback, useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { ActionNeeded } from "../components/dashboard/ActionNeeded";
import { BusinessHighlights } from "../components/dashboard/BusinessHighlights";
import { KPICard } from "../components/dashboard/KPICard";
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

export default function Dashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      setDashboard(await fetchDashboard());
    } catch (requestError) {
      setError(requestError.message || "Unable to load the dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  return (
    <s-page heading="Dashboard">
      <s-section>
        <s-stack direction="inline" gap="base" alignItems="center">
          <s-text tone="subdued">A summary of your store performance.</s-text>
          <s-button
            onClick={loadDashboard}
            {...(isLoading ? { loading: true } : {})}
          >
            Refresh
          </s-button>
        </s-stack>
      </s-section>

      {isLoading && !dashboard ? (
        <s-section heading="Loading dashboard">
          <s-stack direction="inline" gap="base" alignItems="center">
            <s-spinner accessibilityLabel="Loading dashboard data" />
            <s-text>Retrieving your latest store metrics.</s-text>
          </s-stack>
        </s-section>
      ) : null}

      {error ? (
        <s-section heading="Unable to load dashboard">
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
        <BusinessHighlights />
      </s-section>

      <s-section heading="Action needed">
        <ActionNeeded />
      </s-section>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
