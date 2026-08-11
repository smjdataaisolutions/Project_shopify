export const DATE_PRESETS = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "last_7_days", label: "Last 7 days" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "last_90_days", label: "Last 90 days" },
  { value: "this_month", label: "This month" },
  { value: "previous_month", label: "Previous month" },
  { value: "this_year", label: "This year" },
  { value: "custom", label: "Custom range" },
];

export function formatIsoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseIsoDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
  if (!match) return null;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    12,
  );
  return formatIsoDate(date) === value ? date : null;
}

export function getPresetRange(preset, referenceDate = new Date()) {
  const today = new Date(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate(),
    12,
  );
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
  } else if (preset !== "today") {
    return null;
  }

  return { startDate: formatIsoDate(start), endDate: formatIsoDate(end) };
}

export function formatDateRange({ startDate, endDate }) {
  const start = parseIsoDate(startDate);
  const end = parseIsoDate(endDate);
  if (!start || !end) return "All time";

  const yearFormat = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  if (startDate === endDate) return yearFormat.format(start);

  const startFormat = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: start.getFullYear() === end.getFullYear() ? undefined : "numeric",
  });
  return `${startFormat.format(start)}–${yearFormat.format(end)}`;
}

export function pickerValue({ startDate, endDate }) {
  if (!startDate || !endDate) return "";
  return `${startDate}--${endDate}`;
}

export function parsePickerValue(value) {
  if (!value) return { startDate: "", endDate: "" };
  const [startDate, endDate = startDate] = value.split("--");
  return { startDate, endDate };
}

export function monthValue(dateValue) {
  return (dateValue || "").slice(0, 7);
}

export function shiftMonth(value, offset) {
  const [year, month] = value.split("-").map(Number);
  return formatIsoDate(new Date(year, month - 1 + offset, 1, 12)).slice(0, 7);
}
