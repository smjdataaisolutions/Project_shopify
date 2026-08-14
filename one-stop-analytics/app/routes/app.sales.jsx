import { useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { KPICard } from "../components/dashboard/KPICard";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import { RevenueTrend } from "../components/sales/RevenueTrend";
import { SalesActionNeeded } from "../components/sales/SalesActionNeeded";
import {
  AppliedSalesFilters,
  hasSalesFilters,
  SalesFilters,
} from "../components/sales/SalesFilters";
import { DailySalesBreakdown } from "../components/sales/DailySalesBreakdown";
import styles from "../components/dashboard/dashboard.module.css";
import { fetchSalesSummary } from "../services/sales";
import { formatOverviewUpdatedAt } from "../utils/overviewNavigation";
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
      id: "gross-sales",
      label: "Gross sales",
      value: currencyFormatter.format(summary.gross_sales),
      definition: [
        "Definition: Product sales before discounts and refunds.",
        "Formula: SUM(orders.subtotal_price) for matching processed orders.",
      ],
    },
    {
      id: "discounts",
      label: "Discounts",
      value: currencyFormatter.format(summary.discounts),
      definition: [
        "Definition: Discounts applied to matching orders.",
        "Formula: SUM(orders.total_discount).",
      ],
    },
    {
      id: "returns-refunds",
      label: "Returns/refunds",
      value: currencyFormatter.format(summary.returns_refunds ?? 0),
      definition: [
        "Definition: Sales value returned or refunded to customers.",
        "Formula: SUM(orders.total_refunded), attributed to the order processed date.",
      ],
    },
    {
      id: "net-sales",
      label: "Net sales",
      value: currencyFormatter.format(summary.net_sales),
      definition: [
        "Definition: Product sales remaining after discounts and refunds.",
        "Formula: Gross sales − Discounts − Returns/refunds.",
      ],
    },
    {
      id: "shipping",
      label: "Shipping",
      value: currencyFormatter.format(summary.shipping),
      definition: [
        "Definition: Shipping charges collected on matching orders.",
        "Formula: SUM(orders.total_shipping).",
      ],
    },
    {
      id: "taxes",
      label: "Taxes",
      value: currencyFormatter.format(summary.taxes),
      definition: [
        "Definition: Tax collected on matching orders.",
        "Formula: SUM(orders.total_tax).",
      ],
    },
    {
      id: "orders",
      label: "Orders",
      value: summary.orders_count,
      definition: [
        "Definition: Distinct processed orders matching the selected filters.",
        "Formula: COUNT(DISTINCT orders.id).",
      ],
    },
    {
      id: "total-sales",
      label: "Total sales",
      value: currencyFormatter.format(summary.total_sales),
      definition: [
        "Definition: Shopify's final sales amount for matching orders.",
        "Formula: SUM(orders.total_price).",
      ],
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
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [filterOptions, setFilterOptions] = useState(null);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setSummary(null);

    fetchSalesSummary(filters)
      .then((response) => {
        if (active) {
          setSummary(response);
          setLastUpdatedAt(
            response.last_updated_at
              ? new Date(response.last_updated_at)
              : null,
          );
        }
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
      <AnalyticsTopNavigation>
        <s-text tone="subdued">
          Last updated: {formatOverviewUpdatedAt(lastUpdatedAt)}
        </s-text>
        <s-button
          icon="refresh"
          onClick={() => setRequestVersion((version) => version + 1)}
          disabled={isLoading}
          accessibilityLabel="Refresh Sales analytics"
        >
          Refresh
        </s-button>
      </AnalyticsTopNavigation>

      {hasSalesFilters(filters) ? (
        <div className={styles.appliedSalesFilters}>
          <AppliedSalesFilters
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
        <SalesFilters
          filters={filters}
          onChange={setFilters}
          onOptionsChange={setFilterOptions}
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
              <div className={`${styles.grid} ${styles.salesKpiGrid}`}>
                {getMetrics(summary).map((metric) => (
                  <KPICard key={metric.label} {...metric} />
                ))}
              </div>
            </s-section>
          ) : null}

          <s-section heading="Revenue trend">
            <RevenueTrend key={`trend:${requestVersion}`} filters={filters} />
          </s-section>

          <s-section heading="Action needed">
            <SalesActionNeeded
              key={`actions:${requestVersion}`}
              filters={filters}
            />
          </s-section>

          <s-section heading="Daily Sales Breakdown">
            <DailySalesBreakdown
              key={`breakdown:${requestVersion}`}
              filters={filters}
            />
          </s-section>
        </div>
      </div>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
