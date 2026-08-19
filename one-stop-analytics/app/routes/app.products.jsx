import { useEffect, useState } from "react";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { KPICard } from "../components/dashboard/KPICard";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import {
  AppliedProductFilters,
  EMPTY_PRODUCT_FILTERS,
  hasProductFilters,
  ProductFilters,
} from "../components/products/ProductFilters";
import { ProductSalesPerformanceCharts } from "../components/products/ProductSalesPerformanceCharts";
import { ProductPerformanceTable } from "../components/products/ProductPerformanceTable";
import styles from "../components/dashboard/dashboard.module.css";
import { fetchProductKpis } from "../services/products";
import { authenticate } from "../shopify.server";
import { formatOverviewUpdatedAt } from "../utils/overviewNavigation";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

const countFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

function getMetrics(kpis) {
  const topProduct = kpis.top_selling_product;
  return [
    {
      id: "total-products",
      label: "Total Products",
      value: countFormatter.format(kpis.total_products),
      definition: [
        "Definition: Products in the current synchronized catalog matching product filters.",
        "Formula: COUNT(DISTINCT products.id). Date selection does not reconstruct historical catalog state.",
      ],
    },
    {
      id: "total-variants",
      label: "Total Variants",
      value: countFormatter.format(kpis.total_variants),
      definition: [
        "Definition: Variants belonging to current-catalog products matching product filters.",
        "Formula: COUNT(DISTINCT product_variants.id) within the matching product scope.",
      ],
    },
    {
      id: "top-selling-product",
      label: "Top Selling Product",
      value: topProduct?.product_name || "—",
      supportingText: topProduct
        ? `${countFormatter.format(topProduct.units_sold)} units sold`
        : "No sales found",
      imageUrl: topProduct?.image_url || null,
      imageAlt: topProduct ? topProduct.product_name : null,
      definition: [
        "Definition: Matching current-catalog product with the most units sold in the selected date range.",
        "Formula: Product-level SUM(quantity), ranked by units, revenue, then product ID.",
      ],
    },
    {
      id: "products-with-no-sales",
      label: "Products With No Sales",
      value: countFormatter.format(kpis.products_with_no_sales),
      definition: [
        "Definition: Matching current-catalog products without positive-unit sales in the selected date range.",
        "Formula: Total Products − matching products with qualifying sales.",
      ],
    },
  ];
}

export default function Products() {
  const [filters, setFilters] = useState(() => ({
    ...EMPTY_PRODUCT_FILTERS,
    productTypes: [],
    vendors: [],
    statuses: [],
  }));
  const [filterOptions, setFilterOptions] = useState(null);
  const [areFiltersCollapsed, setAreFiltersCollapsed] = useState(false);
  const [kpis, setKpis] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    setKpis(null);

    fetchProductKpis(filters)
      .then((response) => {
        if (active) {
          setKpis(response);
          setFilterOptions(response.filter_options);
          setLastUpdatedAt(new Date());
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load product metrics.");
        }
      })
      .finally(() => active && setIsLoading(false));

    return () => {
      active = false;
    };
  }, [filters, requestVersion]);

  const hasAppliedFilters = hasProductFilters(filters);

  return (
    <s-page heading="Products" inlineSize="large">
      <AnalyticsTopNavigation>
        <s-text tone="subdued">
          Last updated: {formatOverviewUpdatedAt(lastUpdatedAt)}
        </s-text>
        <s-button
          icon="refresh"
          onClick={() => setRequestVersion((version) => version + 1)}
          disabled={isLoading}
          accessibilityLabel="Refresh Products analytics"
        >
          Refresh
        </s-button>
      </AnalyticsTopNavigation>

      {hasAppliedFilters ? (
        <div className={styles.appliedSalesFilters}>
          <AppliedProductFilters filters={filters} onChange={setFilters} />
        </div>
      ) : null}

      <div
        className={`${styles.overviewLayout} ${
          areFiltersCollapsed ? styles.overviewLayoutCollapsed : ""
        }`}
      >
        <ProductFilters
          filters={filters}
          options={filterOptions}
          onChange={setFilters}
          isCollapsed={areFiltersCollapsed}
          onCollapse={() => setAreFiltersCollapsed(true)}
        />

        {areFiltersCollapsed ? (
          <aside className={styles.collapsedFilters} aria-label="Collapsed product filters">
            <s-button
              icon="chevron-right"
              variant="tertiary"
              accessibilityLabel="Expand product filters"
              onClick={() => setAreFiltersCollapsed(false)}
            />
          </aside>
        ) : null}

        <div className={styles.overviewContent}>
          {isLoading && !kpis ? (
            <s-section heading="Loading products">
              <s-stack direction="inline" gap="base" alignItems="center">
                <s-spinner accessibilityLabel="Loading product metrics" />
                <s-text>Retrieving your latest product metrics.</s-text>
              </s-stack>
            </s-section>
          ) : null}

          {error ? (
            <s-section heading="Unable to load products">
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
              {kpis.total_products === 0 ? (
                <s-section heading="No products found">
                  <s-text>
                    {hasAppliedFilters
                      ? "No products match the applied filters."
                      : "No products are available in the current synchronized catalog."}
                  </s-text>
                </s-section>
              ) : null}
              {kpis.total_products > 0 && !kpis.top_selling_product ? (
                <s-section heading="No product sales found">
                  <s-text>
                    No matching products generated sales in the selected date range.
                  </s-text>
                </s-section>
              ) : null}
              <s-section heading="Product Performance">
                <div className={`${styles.grid} ${styles.productKpiGrid}`}>
                  {getMetrics(kpis).map((metric) => (
                    <KPICard key={metric.id} {...metric} />
                  ))}
                </div>
              </s-section>
            </>
          ) : null}

          <ProductSalesPerformanceCharts
            filters={filters}
            refreshKey={requestVersion}
          />
          <ProductPerformanceTable
            filters={filters}
            refreshKey={requestVersion}
          />
        </div>
      </div>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
