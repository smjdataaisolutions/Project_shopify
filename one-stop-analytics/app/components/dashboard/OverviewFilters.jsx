/* eslint-disable react/prop-types */
import { useEffect, useState } from "react";
import { fetchOverviewFilterOptions } from "../../services/dashboard";
import styles from "./overviewFilters.module.css";

const DATE_PRESETS = [
  ["today", "Today"],
  ["yesterday", "Yesterday"],
  ["last_7_days", "Last 7 days"],
  ["last_30_days", "Last 30 days"],
  ["last_90_days", "Last 90 days"],
  ["this_month", "This month"],
  ["previous_month", "Previous month"],
  ["this_year", "This year"],
  ["custom", "Custom range"],
];

const INVENTORY_OPTIONS = [
  [null, "All"],
  ["in_stock", "In stock"],
  ["low_stock", "Low stock"],
  ["out_of_stock", "Out of stock"],
];

function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getPresetRange(preset) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today);
  const end = new Date(today);

  if (preset === "yesterday") {
    start.setDate(start.getDate() - 1);
    end.setDate(end.getDate() - 1);
  } else if (preset === "last_7_days") {
    start.setDate(start.getDate() - 6);
  } else if (preset === "last_30_days") {
    start.setDate(start.getDate() - 29);
  } else if (preset === "last_90_days") {
    start.setDate(start.getDate() - 89);
  } else if (preset === "this_month") {
    start.setDate(1);
  } else if (preset === "previous_month") {
    start.setMonth(start.getMonth() - 1, 1);
    end.setDate(0);
  } else if (preset === "this_year") {
    start.setMonth(0, 1);
  }

  return { startDate: formatDate(start), endDate: formatDate(end) };
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

function MultiSelectGroup({ heading, options, selectedValues, onChange }) {
  if (!options.length) return null;

  const toggle = (value) => {
    onChange(
      selectedValues.includes(value)
        ? selectedValues.filter((item) => item !== value)
        : [...selectedValues, value],
    );
  };

  return (
    <div className={styles.group}>
      <s-heading>{heading}</s-heading>
      <div className={styles.options}>
        {options.map((option) => {
          const value = typeof option === "string" ? option : option.id;
          const label = typeof option === "string" ? option : option.name;
          return (
            <FilterOption
              key={value}
              label={label}
              selected={selectedValues.includes(value)}
              onClick={() => toggle(value)}
            />
          );
        })}
      </div>
    </div>
  );
}

export function OverviewFilters({ filters, onChange, isCollapsed, onCollapse }) {
  const [options, setOptions] = useState(null);
  const [error, setError] = useState(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const [datePreset, setDatePreset] = useState(null);
  const [draftDates, setDraftDates] = useState({ startDate: "", endDate: "" });
  const dateError = draftDates.startDate && draftDates.endDate
    && draftDates.startDate > draftDates.endDate;

  useEffect(() => {
    let active = true;
    setError(null);
    fetchOverviewFilterOptions()
      .then((response) => active && setOptions(response))
      .catch((requestError) => {
        if (active) {
          setError(requestError.message || "Unable to load filter options.");
        }
      });
    return () => { active = false; };
  }, [requestVersion]);

  const selectDatePreset = (preset) => {
    setDatePreset(preset);
    if (preset !== "custom") setDraftDates(getPresetRange(preset));
  };

  const applyDates = () => {
    if (!datePreset || dateError) return;
    onChange({ ...filters, ...draftDates });
  };

  const clearAll = () => {
    setDatePreset(null);
    setDraftDates({ startDate: "", endDate: "" });
    onChange({
      startDate: "",
      endDate: "",
      orderStatuses: [],
      fulfillmentStatuses: [],
      inventoryStatus: null,
      locationIds: [],
    });
  };

  return (
    <aside
      id="store-performance-filters"
      className={`${styles.panel} ${isCollapsed ? styles.panelCollapsed : ""}`}
      aria-label="Store performance filters"
      aria-hidden={isCollapsed}
    >
      <s-box padding="base" borderWidth="base" borderRadius="base" background="base">
        <s-stack direction="block" gap="base">
          <div className={styles.header}>
            <s-heading>Filters</s-heading>
            <div className={styles.headerActions}>
              <s-button variant="tertiary" onClick={clearAll}>Clear all</s-button>
              <s-button
                icon="chevron-left"
                variant="tertiary"
                accessibilityLabel="Collapse filters"
                onClick={onCollapse}
              />
            </div>
          </div>

          <div className={styles.group}>
            <s-heading>Date range</s-heading>
            <div className={styles.options}>
              {DATE_PRESETS.map(([value, label]) => (
                <FilterOption
                  key={value}
                  label={label}
                  selected={datePreset === value}
                  onClick={() => selectDatePreset(value)}
                />
              ))}
            </div>
            {datePreset === "custom" ? (
              <div className={styles.dateFields}>
                <s-date-field
                  label="Start date"
                  value={draftDates.startDate}
                  onChange={(event) => setDraftDates((dates) => ({
                    ...dates,
                    startDate: event.currentTarget.value,
                  }))}
                />
                <s-date-field
                  label="End date"
                  value={draftDates.endDate}
                  onChange={(event) => setDraftDates((dates) => ({
                    ...dates,
                    endDate: event.currentTarget.value,
                  }))}
                />
              </div>
            ) : null}
            {dateError ? (
              <s-text tone="critical">
                Start date must be on or before end date.
              </s-text>
            ) : null}
            <s-button
              variant="primary"
              disabled={
                !datePreset
                || !draftDates.startDate
                || !draftDates.endDate
                || dateError
              }
              onClick={applyDates}
            >
              Apply
            </s-button>
          </div>

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
              <s-spinner accessibilityLabel="Loading filter options" />
              <s-text>Loading filters…</s-text>
            </s-stack>
          ) : null}

          {options ? (
            <>
              <MultiSelectGroup
                heading="Order status"
                options={options.order_statuses}
                selectedValues={filters.orderStatuses}
                onChange={(orderStatuses) => onChange({ ...filters, orderStatuses })}
              />
              <MultiSelectGroup
                heading="Fulfillment status"
                options={options.fulfillment_statuses}
                selectedValues={filters.fulfillmentStatuses}
                onChange={(fulfillmentStatuses) => onChange({
                  ...filters,
                  fulfillmentStatuses,
                })}
              />

              <div className={styles.group}>
                <s-heading>Inventory status</s-heading>
                <div className={styles.options}>
                  {INVENTORY_OPTIONS.map(([value, label]) => (
                    <FilterOption
                      key={label}
                      label={label}
                      selected={filters.inventoryStatus === value}
                      onClick={() => onChange({ ...filters, inventoryStatus: value })}
                    />
                  ))}
                </div>
              </div>

              <MultiSelectGroup
                heading="Location"
                options={options.locations}
                selectedValues={filters.locationIds}
                onChange={(locationIds) => onChange({ ...filters, locationIds })}
              />
            </>
          ) : null}
        </s-stack>
      </s-box>
    </aside>
  );
}
