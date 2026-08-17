from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.repositories.orders_repository import OrderFilters, OrdersRepository
from app.schemas.orders import OrderKpiResponse


FULFILLED_STATUSES = {"FULFILLED"}
PARTIALLY_FULFILLED_STATUSES = {"PARTIAL", "PARTIALLY_FULFILLED"}
UNFULFILLED_STATUSES = {"UNFULFILLED"}
SUPPORTED_ORDER_STATUSES = {"open", "cancelled"}


def build_order_filters(
    start_date: date | None,
    end_date: date | None,
    sales_channels: list[str] | None = None,
    order_statuses: list[str] | None = None,
    fulfillment_statuses: list[str] | None = None,
    payment_statuses: list[str] | None = None,
) -> OrderFilters:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    normalized_order_statuses = tuple(
        dict.fromkeys(status.strip().lower() for status in order_statuses or [])
    )
    unsupported = set(normalized_order_statuses) - SUPPORTED_ORDER_STATUSES
    if unsupported:
        raise ValueError(
            "Unsupported order_status. Choose open or cancelled."
        )
    return OrderFilters(
        start_date=start_date,
        end_date=end_date,
        sales_channels=tuple(dict.fromkeys(sales_channels or [])),
        order_statuses=normalized_order_statuses,
        fulfillment_statuses=tuple(
            dict.fromkeys(fulfillment_statuses or [])
        ),
        payment_statuses=tuple(dict.fromkeys(payment_statuses or [])),
    )


class OrdersService:
    """Business rules for the Orders KPI response."""

    def __init__(self, repository: OrdersRepository) -> None:
        self.repository = repository

    def get_kpis(
        self, filters: OrderFilters = OrderFilters()
    ) -> OrderKpiResponse:
        aggregates = self.repository.get_kpi_aggregates(filters)

        total_orders = sum(row.orders_count or 0 for row in aggregates)
        units_ordered = sum(row.units_ordered or 0 for row in aggregates)
        cancelled_orders = sum(row.cancelled_orders or 0 for row in aggregates)
        refunded_orders = sum(row.refunded_orders or 0 for row in aggregates)
        fulfilled_orders = 0
        partially_fulfilled_orders = 0
        unfulfilled_orders = 0

        for row in aggregates:
            status = self._normalize_status(row.fulfillment_status)
            if status in FULFILLED_STATUSES:
                fulfilled_orders += row.orders_count or 0
            elif status in PARTIALLY_FULFILLED_STATUSES:
                partially_fulfilled_orders += row.orders_count or 0
            elif status in UNFULFILLED_STATUSES:
                unfulfilled_orders += row.orders_count or 0

        eligible_orders = total_orders - cancelled_orders
        fulfillment_rate = (
            Decimal(fulfilled_orders) / Decimal(eligible_orders) * Decimal("100")
            if eligible_orders > 0
            else Decimal("0")
        ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

        return OrderKpiResponse(
            total_orders=total_orders,
            units_ordered=units_ordered,
            unfulfilled_orders=unfulfilled_orders,
            partially_fulfilled_orders=partially_fulfilled_orders,
            fulfilled_orders=fulfilled_orders,
            cancelled_orders=cancelled_orders,
            refunded_orders=refunded_orders,
            fulfillment_rate=float(fulfillment_rate),
        )

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        return "_".join((status or "").strip().upper().replace("-", " ").split())
