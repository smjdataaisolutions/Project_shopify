/* eslint-disable react/prop-types */
import { useEffect, useId, useState } from "react";
import { fetchSalesFilterOptions } from "../../services/sales";
import { DateRangePicker } from "../filters/DateRangePicker";
import styles from "../dashboard/overviewFilters.module.css";

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

function MultiSelectGroup({ heading, options, selectedValues, onChange }) {
  if (!options.length) return null;

  const toggle = (values) => {
    const allSelected = values.every((value) => selectedValues.includes(value));
    const optionValues = new Set(values);
    onChange(
      allSelected
        ? selectedValues.filter((value) => !optionValues.has(value))
        : [...new Set([...selectedValues, ...values])],
    );
  };

  return (
    <CollapsibleFilterSection title={heading}>
      <div className={styles.options}>
        {options.map((option) => {
          const key = typeof option === "string" ? option : option.id;
          const label = typeof option === "string" ? option : option.name;
          const values = typeof option === "string" ? [option] : option.values;
          return (
            <FilterOption
              key={key}
              label={label}
              selected={values.every((value) => selectedValues.includes(value))}
              onClick={() => toggle(values)}
            />
          );
        })}
      </div>
    </CollapsibleFilterSection>
  );
}

export function SalesFilters({ filters, onChange, isCollapsed, onCollapse }) {
  const [options, setOptions] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const [datePreset, setDatePreset] = useState(null);

  useEffect(() => {
    let active = true;
    setError(null);
    fetchSalesFilterOptions()
      .then((response) => active && setOptions(response))
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load sales filters.");
        }
      });
    return () => {
      active = false;
    };
  }, [requestVersion]);

  const clearAll = () => {
    setDatePreset(null);
    onChange({
      startDate: "",
      endDate: "",
      salesChannels: [],
      orderStatuses: [],
      currencies: [],
    });
  };

  return (
    <aside
      id="sales-filters"
      className={`${styles.panel} ${isCollapsed ? styles.panelCollapsed : ""}`}
      aria-label="Sales filters"
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
                accessibilityLabel="Collapse sales filters"
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
              <s-spinner accessibilityLabel="Loading sales filter options" />
              <s-text>Loading filters…</s-text>
            </s-stack>
          ) : null}

          {options ? (
            <>
              <MultiSelectGroup
                heading="Sales channel"
                options={options.sales_channels || []}
                selectedValues={filters.salesChannels}
                onChange={(salesChannels) =>
                  onChange({ ...filters, salesChannels })
                }
              />
              <MultiSelectGroup
                heading="Order status"
                options={options.order_statuses || []}
                selectedValues={filters.orderStatuses}
                onChange={(orderStatuses) =>
                  onChange({ ...filters, orderStatuses })
                }
              />
              <MultiSelectGroup
                heading="Currency"
                options={options.currencies || []}
                selectedValues={filters.currencies}
                onChange={(currencies) => onChange({ ...filters, currencies })}
              />
            </>
          ) : null}
        </s-stack>
      </s-box>
    </aside>
  );
}
