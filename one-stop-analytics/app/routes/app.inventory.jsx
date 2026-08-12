/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import {
  AppliedInventoryFilters,
  EMPTY_INVENTORY_FILTERS,
  hasInventoryFilters,
  InventoryFilters,
} from "../components/inventory/InventoryFilters";
import { InventoryTable } from "../components/inventory/InventoryTable";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import styles from "../components/dashboard/dashboard.module.css";
import { fetchInventoryKpis } from "../services/inventory";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

const countFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const derivedFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

function getMetrics(kpis) {
  return [
    {
      id: "total-inventory-units",
      label: "Total inv. units",
      value: countFormatter.format(kpis.total_inventory_units),
      definition: [
        "Definition: Total sellable units across tracked variant-location inventory items.",
        "Formula: Sum max(available quantity per table row, 0).",
      ],
    },
    {
      id: "in-stock-products",
      label: "In-stock inv. items",
      value: countFormatter.format(kpis.in_stock_products),
      definition: [
        "Definition: Tracked variant-location rows with sellable inventory.",
        "Formula: Count table rows whose available quantity is greater than 0.",
      ],
    },
    {
      id: "low-stock-products",
      label: "Low-stock inv. items",
      value: countFormatter.format(kpis.low_stock_products),
      definition: [
        "Definition: Tracked variant-location rows approaching stockout.",
        "Formula: Count table rows with available quantity from 1 through 10.",
      ],
    },
    {
      id: "out-of-stock-products",
      label: "Out-of-stock inv. items",
      value: countFormatter.format(kpis.out_of_stock_products),
      definition: [
        "Definition: Tracked variant-location rows with no inventory remaining.",
        "Formula: Count table rows whose available quantity equals 0.",
      ],
    },
    {
      id: "sell-through-rate",
      label: "Sell-through rate",
      value:
        kpis.sell_through_rate == null
          ? "\u2014"
          : `${derivedFormatter.format(kpis.sell_through_rate)}%`,
      definition: [
        "Definition: Share of available stock sold during the trailing 30 days.",
        "Formula: Units sold / (units sold + current inventory) x 100.",
      ],
    },
  ];
}

function InventoryKpiCard({ id, label, value, definition }) {
  const tooltipId = `${id}-formula`;

  return (
    <s-box
      padding="base"
      borderWidth="base"
      borderRadius="base"
      background="base"
    >
      <s-stack direction="block" gap="small">
        <s-stack
          direction="inline"
          gap="small"
          alignItems="center"
          justifyContent="space-between"
        >
          <s-text tone="subdued">{label}</s-text>
          <s-button
            icon="info"
            variant="tertiary"
            accessibilityLabel={`How ${label.toLowerCase()} is calculated`}
            interestFor={tooltipId}
          />
          <s-tooltip id={tooltipId}>
            {definition.map((line) => (
              <s-paragraph key={line}>{line}</s-paragraph>
            ))}
          </s-tooltip>
        </s-stack>
        <s-heading>{value}</s-heading>
      </s-stack>
    </s-box>
  );
}

export default function Inventory() {
  const [areFiltersCollapsed, setAreFiltersCollapsed] = useState(false);
  const [filters, setFilters] = useState(() => ({
    ...EMPTY_INVENTORY_FILTERS,
    locationIds: [],
    vendors: [],
    inventoryStatuses: [],
  }));
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

    fetchInventoryKpis(filters)
      .then((response) => {
        if (active) setKpis(response);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load inventory metrics.",
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

  const hasInventoryData =
    kpis && kpis.in_stock_products + kpis.out_of_stock_products > 0;
  const hasAppliedFilters = hasInventoryFilters(filters);
  const filterKey = JSON.stringify(filters);
  const latestInventorySync = filterOptions?.date_range
    ?.latest_inventory_sync_at
    ? new Intl.DateTimeFormat("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(filterOptions.date_range.latest_inventory_sync_at))
    : null;

  return (
    <s-page heading="Inventory" inlineSize="large">
      <AnalyticsTopNavigation />

      <div
        className={`${styles.overviewLayout} ${
          areFiltersCollapsed ? styles.overviewLayoutCollapsed : ""
        }`}
      >
        <InventoryFilters
          appliedFilters={filters}
          onApply={setFilters}
          onOptionsChange={setFilterOptions}
          isCollapsed={areFiltersCollapsed}
          onCollapse={() => setAreFiltersCollapsed(true)}
        />

        {areFiltersCollapsed ? (
          <aside
            className={styles.collapsedFilters}
            aria-label="Collapsed inventory filters"
          >
            <s-button
              icon="chevron-right"
              variant="tertiary"
              accessibilityLabel="Expand inventory filters"
              onClick={() => setAreFiltersCollapsed(false)}
            />
          </aside>
        ) : null}

        <div className={styles.overviewContent}>
          <div className={styles.inventoryContextRow}>
            <AppliedInventoryFilters
              filters={filters}
              options={filterOptions}
              onChange={setFilters}
            />

            {latestInventorySync ? (
              <div className={styles.inventoryAsOf}>
                <s-text tone="subdued">
                  Inventory as of {latestInventorySync}
                </s-text>
              </div>
            ) : null}
          </div>

          {isLoading && !kpis ? (
            <s-section heading="Loading inventory">
              <s-stack direction="inline" gap="base" alignItems="center">
                <s-spinner accessibilityLabel="Loading inventory metrics" />
                <s-text>Retrieving your latest inventory metrics.</s-text>
              </s-stack>
            </s-section>
          ) : null}

          {error ? (
            <s-section heading="Unable to load inventory">
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

          {kpis && !hasInventoryData ? (
            <s-section heading="Inventory overview">
              <s-stack direction="block" gap="small">
                <s-heading>
                  {hasAppliedFilters
                    ? "No inventory matches the applied filters"
                    : "No tracked inventory yet"}
                </s-heading>
                <s-text tone="subdued">
                  {hasAppliedFilters
                    ? "Clear or adjust the filters to see inventory KPIs."
                    : "Inventory KPI cards will appear after tracked product inventory is synchronized."}
                </s-text>
              </s-stack>
            </s-section>
          ) : null}

          {hasInventoryData ? (
            <s-section heading="Inventory overview">
              <div className={styles.grid}>
                {getMetrics(kpis).map((metric) => (
                  <InventoryKpiCard key={metric.id} {...metric} />
                ))}
              </div>
            </s-section>
          ) : null}

          <s-section accessibilityLabel="Inventory details">
            <InventoryTable key={filterKey} filters={filters} />
          </s-section>
        </div>
      </div>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
