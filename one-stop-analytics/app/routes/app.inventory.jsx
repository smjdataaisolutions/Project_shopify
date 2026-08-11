/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
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
      label: "Total inventory units",
      value: countFormatter.format(kpis.total_inventory_units),
      definition: [
        "Definition: Total sellable units across inventory-tracked products.",
        "Formula: Sum max(sum of known variant quantities per product, 0).",
      ],
    },
    {
      id: "in-stock-products",
      label: "In-stock products",
      value: countFormatter.format(kpis.in_stock_products),
      definition: [
        "Definition: Tracked products that currently have sellable inventory.",
        "Formula: Count products whose aggregated inventory is greater than 0.",
      ],
    },
    {
      id: "low-stock-products",
      label: "Low-stock products",
      value: countFormatter.format(kpis.low_stock_products),
      definition: [
        "Definition: Tracked products approaching stockout at the current threshold.",
        "Formula: Count products with aggregated inventory from 1 through 10.",
      ],
    },
    {
      id: "out-of-stock-products",
      label: "Out-of-stock products",
      value: countFormatter.format(kpis.out_of_stock_products),
      definition: [
        "Definition: Tracked products with no sellable inventory remaining.",
        "Formula: Count products whose normalized aggregated inventory equals 0.",
      ],
    },
    {
      id: "sell-through-rate",
      label: "Sell-through rate",
      value:
        kpis.sell_through_rate == null
          ? "—"
          : `${derivedFormatter.format(kpis.sell_through_rate)}%`,
      definition: [
        "Definition: Share of available stock sold during the trailing 30 days.",
        "Formula: Units sold ÷ (units sold + current inventory) × 100.",
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
  const [kpis, setKpis] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setKpis(null);

    fetchInventoryKpis()
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
  }, [requestVersion]);

  const hasInventoryData =
    kpis && kpis.in_stock_products + kpis.out_of_stock_products > 0;

  return (
    <s-page heading="Inventory" inlineSize="large">
      <AnalyticsTopNavigation />

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
            <s-heading>No tracked inventory yet</s-heading>
            <s-text tone="subdued">
              Inventory KPI cards will appear after tracked product inventory
              is synchronized.
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
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
