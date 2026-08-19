/* eslint-disable react/prop-types */
import { useId, useState } from "react";
import { DateRangePicker } from "../filters/DateRangePicker";
import styles from "../dashboard/overviewFilters.module.css";

export const EMPTY_PRODUCT_FILTERS = Object.freeze({
  startDate: "",
  endDate: "",
  productTypes: [],
  vendors: [],
  statuses: [],
});

export function hasProductFilters(filters) {
  return Boolean(
    filters.startDate ||
      filters.endDate ||
      filters.productTypes?.length ||
      filters.vendors?.length ||
      filters.statuses?.length,
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
        {selected ? "✓" : ""}
      </span>
    </button>
  );
}

function CollapsibleFilterSection({ title, children }) {
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
        <span className={styles.sectionTitle}>{title}</span>
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
  if (!options.length) {
    return <s-text tone="subdued">No options available.</s-text>;
  }

  return (
    <div className={styles.options}>
      {options.map((option) => {
        const value = valueFor(option);
        return (
          <FilterOption
            key={value}
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

export function AppliedProductFilters({ filters, onChange }) {
  if (!hasProductFilters(filters)) return null;

  const chips = [
    ...(filters.startDate && filters.endDate
      ? [
          {
            key: "date",
            label: `Date: ${filters.startDate} – ${filters.endDate}`,
            remove: () => onChange({ ...filters, startDate: "", endDate: "" }),
          },
        ]
      : []),
    ...filters.productTypes.map((value) => ({
      key: `type:${value}`,
      label: `Product type: ${value}`,
      remove: () =>
        onChange({
          ...filters,
          productTypes: filters.productTypes.filter((item) => item !== value),
        }),
    })),
    ...filters.vendors.map((value) => ({
      key: `vendor:${value}`,
      label: `Vendor: ${value}`,
      remove: () =>
        onChange({
          ...filters,
          vendors: filters.vendors.filter((item) => item !== value),
        }),
    })),
    ...filters.statuses.map((value) => ({
      key: `status:${value}`,
      label: `Status: ${value === "active" ? "Active" : "Archived"}`,
      remove: () =>
        onChange({
          ...filters,
          statuses: filters.statuses.filter((item) => item !== value),
        }),
    })),
  ];

  return (
    <s-stack direction="inline" gap="small" alignItems="center">
      <s-text tone="subdued">Applied filters:</s-text>
      {chips.map((chip) => (
        <s-button key={chip.key} variant="tertiary" onClick={chip.remove}>
          {chip.label} ×
        </s-button>
      ))}
    </s-stack>
  );
}

export function ProductFilters({
  filters,
  options,
  onChange,
  isCollapsed,
  onCollapse,
}) {
  const [datePreset, setDatePreset] = useState(null);

  const clearAll = () => {
    setDatePreset(null);
    onChange({
      ...EMPTY_PRODUCT_FILTERS,
      productTypes: [],
      vendors: [],
      statuses: [],
    });
  };

  return (
    <aside
      id="product-filters"
      className={`${styles.panel} ${isCollapsed ? styles.panelCollapsed : ""}`}
      aria-label="Product filters"
      aria-hidden={isCollapsed}
    >
      <s-box padding="base" borderWidth="base" borderRadius="base" background="base">
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
                accessibilityLabel="Collapse product filters"
                onClick={onCollapse}
              />
            </div>
          </div>

          <CollapsibleFilterSection title="Date range">
            <DateRangePicker
              appliedRange={{
                startDate: filters.startDate,
                endDate: filters.endDate,
              }}
              appliedPreset={datePreset}
              onApply={({ range, preset }) => {
                setDatePreset(preset);
                onChange({ ...filters, ...range });
              }}
            />
          </CollapsibleFilterSection>

          <CollapsibleFilterSection title="Product type">
            <MultiSelect
              options={options?.product_types || []}
              selectedValues={filters.productTypes}
              valueFor={(option) => option}
              labelFor={(option) => option}
              onChange={(productTypes) => onChange({ ...filters, productTypes })}
            />
          </CollapsibleFilterSection>

          <CollapsibleFilterSection title="Vendor">
            <MultiSelect
              options={options?.vendors || []}
              selectedValues={filters.vendors}
              valueFor={(option) => option}
              labelFor={(option) => option}
              onChange={(vendors) => onChange({ ...filters, vendors })}
            />
          </CollapsibleFilterSection>

          <CollapsibleFilterSection title="Status">
            <MultiSelect
              options={options?.statuses || []}
              selectedValues={filters.statuses}
              valueFor={(option) => option.value}
              labelFor={(option) => option.label}
              onChange={(statuses) => onChange({ ...filters, statuses })}
            />
          </CollapsibleFilterSection>
        </s-stack>
      </s-box>
    </aside>
  );
}
