/* eslint-disable react/prop-types */
import { useId, useState } from "react";
import {
  DATE_PRESETS,
  formatDateRange,
  formatIsoDate,
  getPresetRange,
  monthValue,
  parseIsoDate,
  parsePickerValue,
  pickerValue,
  shiftMonth,
} from "../../utils/dateRanges";
import styles from "./dateRangePicker.module.css";

function initialDraft(appliedRange, appliedPreset) {
  if (parseIsoDate(appliedRange.startDate) && parseIsoDate(appliedRange.endDate)) {
    return { range: appliedRange, preset: appliedPreset || "custom" };
  }
  return { range: { startDate: "", endDate: "" }, preset: null };
}

function initialView(range) {
  const endMonth = monthValue(range.endDate || formatIsoDate(new Date()));
  return shiftMonth(endMonth, -1);
}

export function DateRangePicker({ appliedRange, appliedPreset, onApply }) {
  const popoverId = `analytics-date-range-${useId().replaceAll(":", "")}`;
  const initial = initialDraft(appliedRange, appliedPreset);
  const [draftRange, setDraftRange] = useState(initial.range);
  const [draftPreset, setDraftPreset] = useState(initial.preset);
  const [viewMonth, setViewMonth] = useState(initialView(initial.range));
  const today = formatIsoDate(new Date());
  const allowedThroughToday = `--${today}`;
  const start = parseIsoDate(draftRange.startDate);
  const end = parseIsoDate(draftRange.endDate);
  const isInvalid =
    !start ||
    !end ||
    draftRange.startDate > draftRange.endDate ||
    draftRange.startDate > today ||
    draftRange.endDate > today;
  const showDateError =
    Boolean(draftRange.startDate || draftRange.endDate) && isInvalid;

  const restoreAppliedRange = () => {
    const next = initialDraft(appliedRange, appliedPreset);
    setDraftRange(next.range);
    setDraftPreset(next.preset);
    setViewMonth(initialView(next.range));
  };

  const selectPreset = (preset) => {
    setDraftPreset(preset);
    if (preset === "custom") return;
    const range = getPresetRange(preset);
    setDraftRange(range);
    setViewMonth(initialView(range));
  };

  const updateDraftRange = (range) => {
    setDraftPreset("custom");
    setDraftRange(range);
  };

  const updateDateField = (field, value) => {
    const range = { ...draftRange, [field]: value };
    updateDraftRange(range);
    if (parseIsoDate(value)) setViewMonth(initialView(range));
  };

  const apply = () => {
    if (!isInvalid) onApply({ range: draftRange, preset: draftPreset });
  };

  const yesterday = getPresetRange("yesterday");
  const triggerLabel =
    appliedPreset === "today" &&
    appliedRange.startDate === today &&
    appliedRange.endDate === today
      ? "Today"
      : appliedPreset === "yesterday" &&
          appliedRange.startDate === yesterday.startDate &&
          appliedRange.endDate === yesterday.endDate
        ? "Yesterday"
        : formatDateRange(appliedRange);

  return (
    <div className={styles.root}>
      <s-button
        icon="calendar"
        commandFor={popoverId}
        command="--toggle"
        accessibilityLabel={`Choose date range. Currently ${triggerLabel}`}
      >
        {triggerLabel} ▾
      </s-button>

      <s-popover
        id={popoverId}
        inlineSize="auto"
        maxInlineSize="100%"
        maxBlockSize="90vh"
        onShow={restoreAppliedRange}
      >
        <div className={styles.popoverContent}>
          <div className={styles.presetColumn}>
            <s-text><strong>Presets</strong></s-text>
            <div className={styles.presetList}>
              {DATE_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  className={`${styles.presetButton} ${
                    draftPreset === preset.value ? styles.presetSelected : ""
                  }`}
                  aria-pressed={draftPreset === preset.value}
                  onClick={() => selectPreset(preset.value)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.calendarColumn}>
            <div className={styles.dateFields}>
              <s-date-field
                label="Start date"
                value={draftRange.startDate}
                allow={allowedThroughToday}
                onChange={(event) =>
                  updateDateField("startDate", event.currentTarget.value)
                }
              />
              <span className={styles.dateArrow} aria-hidden="true">→</span>
              <s-date-field
                label="End date"
                value={draftRange.endDate}
                allow={allowedThroughToday}
                onChange={(event) =>
                  updateDateField("endDate", event.currentTarget.value)
                }
              />
            </div>

            <div className={styles.calendars}>
              <s-date-picker
                type="range"
                value={pickerValue(draftRange)}
                view={viewMonth}
                allow={allowedThroughToday}
                onViewChange={(event) => setViewMonth(event.currentTarget.view)}
                onChange={(event) =>
                  updateDraftRange(parsePickerValue(event.currentTarget.value))
                }
              />
              <div className={styles.secondCalendar}>
                <s-date-picker
                  type="range"
                  value={pickerValue(draftRange)}
                  view={shiftMonth(viewMonth, 1)}
                  allow={allowedThroughToday}
                  onViewChange={(event) =>
                    setViewMonth(shiftMonth(event.currentTarget.view, -1))
                  }
                  onChange={(event) =>
                    updateDraftRange(parsePickerValue(event.currentTarget.value))
                  }
                />
              </div>
            </div>

            {showDateError ? (
              <s-text tone="critical">
                Select a valid range ending today or earlier.
              </s-text>
            ) : null}

            <div className={styles.actions}>
              <s-button
                commandFor={popoverId}
                command="--hide"
                onClick={restoreAppliedRange}
              >
                Cancel
              </s-button>
              <s-button
                variant="primary"
                disabled={isInvalid}
                commandFor={popoverId}
                command="--hide"
                onClick={apply}
              >
                Apply
              </s-button>
            </div>
          </div>
        </div>
      </s-popover>
    </div>
  );
}
