import assert from "node:assert/strict";
import test from "node:test";

import {
  formatDateRange,
  getPresetRange,
  parsePickerValue,
  pickerValue,
} from "../app/utils/dateRanges.js";

const referenceDate = new Date(2026, 7, 11, 12);
const expectedPresets = {
  today: ["2026-08-11", "2026-08-11"],
  yesterday: ["2026-08-10", "2026-08-10"],
  last_7_days: ["2026-08-05", "2026-08-11"],
  last_30_days: ["2026-07-13", "2026-08-11"],
  last_90_days: ["2026-05-14", "2026-08-11"],
  this_month: ["2026-08-01", "2026-08-11"],
  previous_month: ["2026-07-01", "2026-07-31"],
  this_year: ["2026-01-01", "2026-08-11"],
};

for (const [preset, [startDate, endDate]] of Object.entries(expectedPresets)) {
  test(`${preset} calculates the expected inclusive range`, () => {
    assert.deepEqual(getPresetRange(preset, referenceDate), {
      startDate,
      endDate,
    });
  });
}

test("custom picker values preserve the selected ISO range", () => {
  const range = { startDate: "2026-07-01", endDate: "2026-08-11" };
  assert.equal(pickerValue(range), "2026-07-01--2026-08-11");
  assert.deepEqual(parsePickerValue(pickerValue(range)), range);
});

test("visible ranges use compact merchant-friendly formatting", () => {
  assert.equal(
    formatDateRange({ startDate: "2026-07-01", endDate: "2026-08-11" }),
    "Jul 1–Aug 11, 2026",
  );
  assert.equal(
    formatDateRange({ startDate: "2026-08-11", endDate: "2026-08-11" }),
    "Aug 11, 2026",
  );
});
