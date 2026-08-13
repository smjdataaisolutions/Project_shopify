/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import {
  downloadInventoryTableCsv,
  fetchInventoryTable,
} from "../../services/inventory";
import { hasInventoryFilters } from "./InventoryFilters";
import styles from "./inventoryTable.module.css";

const PAGE_SIZE = 25;
const numberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

const STATUS_PRESENTATION = {
  healthy: { label: "In stock", tone: "success" },
  low_stock: { label: "Low stock", tone: "caution" },
  out_of_stock: { label: "Out of stock", tone: "critical" },
  negative: { label: "Negative inventory", tone: "critical" },
  untracked: { label: "Untracked", tone: "info" },
  unknown: { label: "Quantity unavailable", tone: "neutral" },
};

function InventoryStatus({ item }) {
  const presentation =
    STATUS_PRESENTATION[item.inventory_status] || STATUS_PRESENTATION.unknown;

  return <s-badge tone={presentation.tone}>{presentation.label}</s-badge>;
}

export function InventoryTable({
  filters,
  level = "variant",
  onProductSelect,
}) {
  const isProductLevel = level === "product";
  const [page, setPage] = useState(1);
  const [sortOrder, setSortOrder] = useState("asc");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [requestVersion, setRequestVersion] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);

    fetchInventoryTable({
      page,
      pageSize: PAGE_SIZE,
      sortOrder,
      filters,
      level,
    })
      .then((response) => {
        if (active) setResult(response);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load inventory details.",
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [filters, level, page, requestVersion, sortOrder]);

  const toggleInventoryUnitsSort = () => {
    setPage(1);
    setSortOrder((currentOrder) =>
      currentOrder === "asc" ? "desc" : "asc",
    );
  };

  const downloadTable = async () => {
    setDownloadError(null);
    setIsDownloading(true);
    try {
      await downloadInventoryTableCsv({ sortOrder, filters, level });
    } catch (requestError) {
      setDownloadError(
        requestError.message || "Unable to download inventory details.",
      );
    } finally {
      setIsDownloading(false);
    }
  };

  if (isLoading && !result) {
    return (
      <s-stack direction="inline" gap="base" alignItems="center">
        <s-spinner accessibilityLabel="Loading inventory details" />
        <s-text>
          {isProductLevel
            ? "Retrieving inventory by product."
            : "Retrieving inventory by variant and location."}
        </s-text>
      </s-stack>
    );
  }

  if (error) {
    return (
      <s-stack direction="block" gap="base">
        <s-text tone="critical">{error}</s-text>
        <s-button
          onClick={() => setRequestVersion((version) => version + 1)}
        >
          Try again
        </s-button>
      </s-stack>
    );
  }

  if (!result?.items.length) {
    const isFiltered = hasInventoryFilters(filters);
    return (
      <s-stack direction="block" gap="small">
        <s-heading>
          {isFiltered
            ? "No inventory matches the applied filters"
            : "No inventory records yet"}
        </s-heading>
        <s-text tone="subdued">
          {isFiltered
            ? "Clear or adjust the filters to see inventory records."
            : isProductLevel
              ? "Product inventory will appear after Shopify inventory is synchronized."
              : "Variant and location inventory will appear after Shopify inventory is synchronized."}
        </s-text>
      </s-stack>
    );
  }

  const { pagination } = result;

  return (
    <s-stack direction="block" gap="base">
      <s-stack
        direction="inline"
        alignItems="center"
        justifyContent="space-between"
      >
        <s-heading>Inventory details</s-heading>
        <s-button
          icon="download"
          variant="tertiary"
          loading={isDownloading}
          accessibilityLabel="Download all inventory details as CSV"
          onClick={downloadTable}
        />
      </s-stack>
      {downloadError ? (
        <s-text tone="critical">{downloadError}</s-text>
      ) : null}
      <s-table
        variant="auto"
        paginate
        loading={isLoading}
        hasPreviousPage={pagination.page > 1}
        hasNextPage={pagination.page < pagination.total_pages}
        onPreviousPage={() => setPage(pagination.page - 1)}
        onNextPage={() => setPage(pagination.page + 1)}
      >
        <s-table-header-row>
          <s-table-header listSlot="primary">
            Product
          </s-table-header>
          {!isProductLevel ? (
            <s-table-header listSlot="secondary">Variant</s-table-header>
          ) : null}
          <s-table-header listSlot="labeled" format="base">
            <s-stack direction="inline" gap="small" alignItems="center">
              <s-text>Inventory Units</s-text>
              <s-button
                icon={
                  sortOrder === "asc" ? "sort-ascending" : "sort-descending"
                }
                variant="tertiary"
                accessibilityLabel={`Sorted ${sortOrder === "asc" ? "ascending" : "descending"}. Sort inventory units ${sortOrder === "asc" ? "descending" : "ascending"}.`}
                onClick={toggleInventoryUnitsSort}
              />
            </s-stack>
          </s-table-header>
          <s-table-header listSlot="labeled">
            Inventory Status
          </s-table-header>
          {!isProductLevel ? (
            <s-table-header listSlot="secondary">Location</s-table-header>
          ) : null}
        </s-table-header-row>
        <s-table-body>
          {result.items.map((item) => (
            <s-table-row
              key={
                isProductLevel
                  ? item.product_id
                  : `${item.variant_id}:${item.location_id || "unassigned"}`
              }
            >
              <s-table-cell>
                {item.product_id && onProductSelect ? (
                  <button
                    type="button"
                    className={styles.productLink}
                    onClick={() => onProductSelect(item)}
                    aria-label={`View variants for ${item.product}`}
                  >
                    {item.product}
                  </button>
                ) : (
                  item.product
                )}
              </s-table-cell>
              {!isProductLevel ? (
                <s-table-cell>{item.variant}</s-table-cell>
              ) : null}
              <s-table-cell>
                {item.inventory_units == null
                  ? "—"
                  : numberFormatter.format(item.inventory_units)}
              </s-table-cell>
              <s-table-cell>
                <InventoryStatus item={item} />
              </s-table-cell>
              {!isProductLevel ? (
                <s-table-cell>{item.location || "Not assigned"}</s-table-cell>
              ) : null}
            </s-table-row>
          ))}
          <s-table-row>
            <s-table-cell>
              <strong>Total inventory units</strong>
            </s-table-cell>
            {!isProductLevel ? <s-table-cell>-</s-table-cell> : null}
            <s-table-cell>
              <strong>
                {numberFormatter.format(result.totals.total_inventory_units)}
              </strong>
            </s-table-cell>
            <s-table-cell>-</s-table-cell>
            {!isProductLevel ? <s-table-cell>-</s-table-cell> : null}
          </s-table-row>
        </s-table-body>
      </s-table>
      <div className={styles.paginationSummary}>
        <s-text tone="subdued">
          Page {pagination.page} of {pagination.total_pages} ·{" "}
          {numberFormatter.format(pagination.total_items)} inventory records
        </s-text>
      </div>
    </s-stack>
  );
}
