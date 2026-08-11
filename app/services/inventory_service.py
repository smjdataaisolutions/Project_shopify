from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.repositories.inventory_repository import InventoryRepository
from app.schemas.inventory import InventoryKpiResponse


SALES_WINDOW_DAYS = 30
ONE_DECIMAL = Decimal("0.1")


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

    def get_kpis(self) -> InventoryKpiResponse:
        end_date = self.today()
        start_date = end_date - timedelta(days=SALES_WINDOW_DAYS - 1)
        inputs = self.repository.get_kpi_inputs(
            start_date,
            end_date,
            self.low_stock_threshold,
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


def _round_one_decimal(value: Decimal) -> float:
    return float(value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP))
