/* eslint-disable react/prop-types */
import { useEffect, useId, useState } from "react";
import { fetchInventoryFilterOptions } from "../../services/inventory";
import styles from "../dashboard/overviewFilters.module.css";

export const EMPTY_INVENTORY_FILTERS = Object.freeze({
  locationIds: [],
  vendors: [],
  inventoryTracked: null,
  inventoryStatuses: [],
});

function copyFilters(filters) {
  return {
    locationIds: [...(filters.locationIds || [])],
    vendors: [...(filters.vendors || [])],
    inventoryTracked: filters.inventoryTracked ?? null,
    inventoryStatuses: [...(filters.inventoryStatuses || [])],
  };
}

export function hasInventoryFilters(filters) {
  return Boolean(
    filters.locationIds?.length ||
      filters.vendors?.length ||
      filters.inventoryTracked !== null ||
      filters.inventoryStatuses?.length,
  );
}

function FilterOption({ label, selected, onClick }) {
  return (
    <button
      type="button"
      className={`${styles.option} ${selected ? styles.selected : ""}`}
      aria-pressed={selected}
      onClick={onClick}
    >
      <span>{label}</span>
      <span className={styles.check} aria-hidden="true">
        {selected ? "\u2713" : ""}
      </span>
    </button>
  );
}

function CollapsibleFilterSection({ title, unavailable = false, children }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contentId = useId();

  return (
    <div className={styles.group}>
      <button
        type="button"
        className={styles.sectionHeader}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        onClick={() => setIsExpanded((expanded) => !expanded)}
      >
        <span className={styles.sectionTitle}>
          {title}
          {unavailable ? " (Unavailable)" : ""}
        </span>
        <span
          className={`${styles.chevron} ${
            isExpanded ? styles.chevronExpanded : ""
          }`}
          aria-hidden="true"
        />
      </button>
      {isExpanded ? (
        <div id={contentId} className={styles.sectionContent}>
          {children}
        </div>
      ) : null}
    </div>
  );
}

function MultiSelect({ options, selectedValues, valueFor, labelFor, onChange }) {
  return (
    <div className={styles.options}>
      {options.map((option) => {
        const value = valueFor(option);
        return (
          <FilterOption
            key={String(value)}
            label={labelFor(option)}
            selected={selectedValues.includes(value)}
            onClick={() =>
              onChange(
                selectedValues.includes(value)
                  ? selectedValues.filter((item) => item !== value)
                  : [...selectedValues, value],
              )
            }
          />
        );
      })}
    </div>
  );
}

export function AppliedInventoryFilters({ filters, options, onChange }) {
  if (!hasInventoryFilters(filters)) return null;

  const locationNames = new Map(
    (options?.locations || []).map((location) => [location.id, location.name]),
  );
  const statusLabels = new Map(
    (options?.inventory_statuses || []).map((status) => [
      status.value,
      status.label,
    ]),
  );
  const chips = [
    ...(filters.locationIds || []).map((value) => ({
      key: `location:${value}`,
      label: `Location: ${locationNames.get(value) || value}`,
      remove: () =>
        onChange({
          ...filters,
          locationIds: filters.locationIds.filter((item) => item !== value),
        }),
    })),
    ...(filters.vendors || []).map((value) => ({
      key: `vendor:${value}`,
      label: `Vendor: ${value}`,
      remove: () =>
        onChange({
          ...filters,
          vendors: filters.vendors.filter((item) => item !== value),
        }),
    })),
    ...(filters.inventoryTracked === null
      ? []
      : [
          {
            key: "tracked",
            label: filters.inventoryTracked ? "Tracked" : "Untracked",
            remove: () => onChange({ ...filters, inventoryTracked: null }),
          },
        ]),
    ...(filters.inventoryStatuses || []).map((value) => ({
      key: `status:${value}`,
      label: `Status: ${statusLabels.get(value) || value}`,
      remove: () =>
        onChange({
          ...filters,
          inventoryStatuses: filters.inventoryStatuses.filter(
            (item) => item !== value,
          ),
        }),
    })),
  ];

  return (
    <s-stack direction="inline" gap="small" alignItems="center">
      <s-text tone="subdued">Applied filters:</s-text>
      {chips.map((chip) => (
        <s-button key={chip.key} variant="tertiary" onClick={chip.remove}>
          {chip.label} {"\u00d7"}
        </s-button>
      ))}
    </s-stack>
  );
}

export function InventoryFilters({
  appliedFilters,
  onApply,
  onOptionsChange,
  isCollapsed,
  onCollapse,
}) {
  const [options, setOptions] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setError(null);
    fetchInventoryFilterOptions()
      .then((response) => {
        if (active) {
          setOptions(response);
          onOptionsChange(response);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.message || "Unable to load inventory filters.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [onOptionsChange, requestVersion]);

  const clearAll = () => {
    const emptyFilters = copyFilters(EMPTY_INVENTORY_FILTERS);
    onApply(emptyFilters);
  };

  return (
    <aside
      id="inventory-filters"
      className={`${styles.panel} ${isCollapsed ? styles.panelCollapsed : ""}`}
      aria-label="Inventory filters"
      aria-hidden={isCollapsed}
    >
      <s-box
        padding="base"
        borderWidth="base"
        borderRadius="base"
        background="base"
      >
        <s-stack direction="block" gap="small">
          <div className={styles.header}>
            <s-heading>Filters</s-heading>
            <div className={styles.headerActions}>
              <s-button variant="tertiary" onClick={clearAll}>
                Clear all
              </s-button>
              <s-button
                icon="chevron-left"
                variant="tertiary"
                accessibilityLabel="Collapse inventory filters"
                onClick={onCollapse}
              />
            </div>
          </div>

          <CollapsibleFilterSection title="Date range" unavailable>
            <s-text tone="subdued">
              {options?.date_range?.message ||
                "Historical inventory data is not available. Showing the latest inventory position."}
            </s-text>
          </CollapsibleFilterSection>

          {error ? (
            <s-stack direction="block" gap="small">
              <s-text tone="critical">{error}</s-text>
              <s-button onClick={() => setRequestVersion((value) => value + 1)}>
                Try again
              </s-button>
            </s-stack>
          ) : null}

          {!options && !error ? (
            <s-stack direction="inline" gap="small" alignItems="center">
              <s-spinner accessibilityLabel="Loading inventory filter options" />
              <s-text>Loading filters...</s-text>
            </s-stack>
          ) : null}

          <CollapsibleFilterSection title="Location">
            {options?.locations?.length ? (
              <MultiSelect
                options={options.locations}
                selectedValues={appliedFilters.locationIds}
                valueFor={(option) => option.id}
                labelFor={(option) => option.name}
                onChange={(locationIds) =>
                  onApply({ ...appliedFilters, locationIds })
                }
              />
            ) : (
              <s-text tone="subdued">No locations available.</s-text>
            )}
          </CollapsibleFilterSection>

          <CollapsibleFilterSection title="Vendor">
            {options?.vendors?.length ? (
              <MultiSelect
                options={options.vendors}
                selectedValues={appliedFilters.vendors}
                valueFor={(option) => option}
                labelFor={(option) => option}
                onChange={(vendors) =>
                  onApply({ ...appliedFilters, vendors })
                }
              />
            ) : (
              <s-text tone="subdued">No vendors available.</s-text>
            )}
          </CollapsibleFilterSection>

          <CollapsibleFilterSection title="Collection" unavailable>
            <s-text tone="subdued">
              {options?.collections?.message ||
                "Collection filtering is unavailable because collection membership is not present in the current PostgreSQL dataset."}
            </s-text>
          </CollapsibleFilterSection>

          <CollapsibleFilterSection title="Inventory tracked">
            <div className={styles.options}>
              {(options?.inventory_tracked || []).map((option) => (
                <FilterOption
                  key={String(option.value)}
                  label={option.label}
                  selected={appliedFilters.inventoryTracked === option.value}
                  onClick={() =>
                    onApply({
                      ...appliedFilters,
                      inventoryTracked:
                        appliedFilters.inventoryTracked === option.value
                          ? null
                          : option.value,
                    })
                  }
                />
              ))}
            </div>
          </CollapsibleFilterSection>

          <CollapsibleFilterSection title="Inventory status">
            <MultiSelect
              options={options?.inventory_statuses || []}
              selectedValues={appliedFilters.inventoryStatuses}
              valueFor={(option) => option.value}
              labelFor={(option) => option.label}
              onChange={(inventoryStatuses) =>
                onApply({ ...appliedFilters, inventoryStatuses })
              }
            />
          </CollapsibleFilterSection>
        </s-stack>
      </s-box>
    </aside>
  );
}
