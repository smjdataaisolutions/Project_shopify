import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import io

from app.repositories.inventory_repository import (
    InventoryFilters,
    InventoryRepository,
    InventoryTableRow,
)
from app.schemas.inventory import (
    InventoryCollectionCapability,
    InventoryDateRangeCapability,
    InventoryFilterChoice,
    InventoryFilterOptionsResponse,
    InventoryKpiResponse,
    InventoryLocationFilterOption,
    InventoryTableItem,
    InventoryTablePagination,
    InventoryTableResponse,
    InventoryTableTotals,
)


SALES_WINDOW_DAYS = 30
ONE_DECIMAL = Decimal("0.1")
INVENTORY_CSV_COLUMNS = (
    "Product",
    "Variant",
    "Inventory Units",
    "Inventory Status",
    "Location",
)
INVENTORY_STATUS_LABELS = {
    "healthy": "In stock",
    "low_stock": "Low stock",
    "out_of_stock": "Out of stock",
    "negative": "Negative inventory",
    "untracked": "Untracked",
    "unknown": "Quantity unavailable",
}
INVENTORY_STATUS_OPTIONS = tuple(
    InventoryFilterChoice(label=label, value=value)
    for value, label in INVENTORY_STATUS_LABELS.items()
)
INVENTORY_TRACKED_OPTIONS = (
    InventoryFilterChoice(label="Tracked", value=True),
    InventoryFilterChoice(label="Untracked", value=False),
)
INVENTORY_HISTORY_UNAVAILABLE_MESSAGE = (
    "Historical inventory data is not available. Showing the latest inventory "
    "position."
)
COLLECTION_UNAVAILABLE_MESSAGE = (
    "Collection filtering is unavailable because collection membership is not "
    "present in the current PostgreSQL dataset."
)


@dataclass(frozen=True)
class InventoryTableCsvExport:
    filename: str
    content: str


class InventoryService:
    """Business calculations for Inventory KPI cards."""

    def __init__(
        self,
        repository: InventoryRepository,
        low_stock_threshold: int,
        today: Callable[[], date] | None = None,
    ) -> None:
        self.repository = repository
        self.low_stock_threshold = low_stock_threshold
        self.today = today or (lambda: datetime.now(timezone.utc).date())

    def get_filter_options(self) -> InventoryFilterOptionsResponse:
        options = self.repository.get_filter_options()
        return InventoryFilterOptionsResponse(
            locations=[
                InventoryLocationFilterOption(id=location.id, name=location.name)
                for location in options.locations
            ],
            vendors=options.vendors,
            collections=InventoryCollectionCapability(
                message=COLLECTION_UNAVAILABLE_MESSAGE,
            ),
            inventory_tracked=list(INVENTORY_TRACKED_OPTIONS),
            inventory_statuses=list(INVENTORY_STATUS_OPTIONS),
            date_range=InventoryDateRangeCapability(
                message=INVENTORY_HISTORY_UNAVAILABLE_MESSAGE,
                latest_inventory_sync_at=options.latest_inventory_sync_at,
            ),
        )

    def get_kpis(
        self,
        filters: InventoryFilters = InventoryFilters(),
    ) -> InventoryKpiResponse:
        end_date = self.today()
        start_date = end_date - timedelta(days=SALES_WINDOW_DAYS - 1)
        inputs = self.repository.get_kpi_inputs(
            start_date,
            end_date,
            self.low_stock_threshold,
            filters,
        )

        inventory_units = Decimal(inputs.total_inventory_units)
        units_sold = Decimal(inputs.units_sold)
        available_and_sold = inventory_units + units_sold

        sell_through_rate = None
        if available_and_sold > 0:
            sell_through_rate = _round_one_decimal(
                units_sold / available_and_sold * Decimal("100")
            )

        days_remaining = None
        if units_sold > 0:
            average_daily_units_sold = units_sold / Decimal(SALES_WINDOW_DAYS)
            days_remaining = _round_one_decimal(
                inventory_units / average_daily_units_sold
            )

        return InventoryKpiResponse(
            total_inventory_units=inputs.total_inventory_units,
            in_stock_products=inputs.in_stock_products,
            low_stock_products=inputs.low_stock_products,
            out_of_stock_products=inputs.out_of_stock_products,
            sell_through_rate=sell_through_rate,
            days_of_inventory_remaining=days_remaining,
        )

    def get_inventory_table(
        self,
        page: int,
        page_size: int,
        sort_order: str = "asc",
        filters: InventoryFilters = InventoryFilters(),
    ) -> InventoryTableResponse:
        result = self.repository.get_inventory_table(
            page,
            page_size,
            sort_order,
            filters,
            self.low_stock_threshold,
        )
        total_pages = (
            (result.total_items + page_size - 1) // page_size
            if result.total_items
            else 0
        )
        return InventoryTableResponse(
            items=[self._build_table_item(row) for row in result.rows],
            pagination=InventoryTablePagination(
                page=page,
                page_size=page_size,
                total_items=result.total_items,
                total_pages=total_pages,
            ),
            totals=InventoryTableTotals(
                total_inventory_units=result.total_inventory_units,
            ),
        )

    def _build_table_item(self, row: InventoryTableRow) -> InventoryTableItem:
        tracked = row.inventory_tracked is True
        return InventoryTableItem(
            variant_id=row.variant_id,
            location_id=row.location_id,
            product=_clean_text(row.product_title) or "Unnamed product",
            variant=_format_variant_name(row.variant_title),
            inventory_units=row.inventory_units,
            location=_first_non_empty(
                row.location_name,
                row.inventory_location_name,
            ),
            inventory_tracked=tracked,
            inventory_status=_inventory_status(
                row.inventory_units,
                tracked,
                self.low_stock_threshold,
            ),
        )

    def get_inventory_table_export(
        self,
        sort_order: str = "asc",
        filters: InventoryFilters = InventoryFilters(),
    ) -> InventoryTableCsvExport:
        rows = self.repository.get_inventory_table_export(
            sort_order,
            filters,
            self.low_stock_threshold,
        )
        output = io.StringIO(newline="")
        writer = csv.DictWriter(
            output,
            fieldnames=INVENTORY_CSV_COLUMNS,
            lineterminator="\r\n",
        )
        writer.writeheader()
        for row in rows:
            item = self._build_table_item(row)
            writer.writerow(
                {
                    "Product": _csv_safe(item.product),
                    "Variant": _csv_safe(item.variant),
                    "Inventory Units": (
                        "" if item.inventory_units is None else item.inventory_units
                    ),
                    "Inventory Status": INVENTORY_STATUS_LABELS[
                        item.inventory_status
                    ],
                    "Location": _csv_safe(item.location or "Not assigned"),
                }
            )
        return InventoryTableCsvExport(
            filename="inventory-details.csv",
            content=output.getvalue(),
        )


def build_inventory_filters(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    location_ids: list[str] | None = None,
    vendors: list[str] | None = None,
    collection_ids: list[str] | None = None,
    inventory_tracked: bool | None = None,
    inventory_statuses: list[str] | None = None,
) -> InventoryFilters:
    """Validate API query values and build the repository filter contract."""
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")
    if start_date or end_date:
        raise ValueError(INVENTORY_HISTORY_UNAVAILABLE_MESSAGE)

    cleaned_collections = _clean_filter_values(collection_ids)
    if cleaned_collections:
        raise ValueError(COLLECTION_UNAVAILABLE_MESSAGE)

    cleaned_statuses = _clean_filter_values(inventory_statuses)
    supported_statuses = set(INVENTORY_STATUS_LABELS)
    unsupported_statuses = sorted(set(cleaned_statuses) - supported_statuses)
    if unsupported_statuses:
        raise ValueError(
            "Unsupported inventory status: " + ", ".join(unsupported_statuses)
        )

    return InventoryFilters(
        location_ids=_clean_filter_values(location_ids),
        vendors=_clean_filter_values(vendors),
        inventory_tracked=inventory_tracked,
        inventory_statuses=cleaned_statuses,
    )


def _round_one_decimal(value: Decimal) -> float:
    return float(value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP))


def _format_variant_name(variant_title: str | None) -> str:
    variant = _clean_text(variant_title)
    if variant and variant.casefold() == "default title":
        return "Default"
    return variant or "Unnamed variant"


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_filter_values(values: list[str] | None) -> tuple[str, ...]:
    cleaned = {
        value.strip()
        for value in (values or [])
        if value is not None and value.strip()
    }
    return tuple(sorted(cleaned, key=str.casefold))


def _inventory_status(
    inventory_units: int | None,
    inventory_tracked: bool,
    low_stock_threshold: int,
) -> str:
    if not inventory_tracked:
        return "untracked"
    if inventory_units is None:
        return "unknown"
    if inventory_units < 0:
        return "negative"
    if inventory_units == 0:
        return "out_of_stock"
    if inventory_units <= low_stock_threshold:
        return "low_stock"
    return "healthy"


def _csv_safe(value: str) -> str:
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value
