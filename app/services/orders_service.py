from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.repositories.orders_repository import (
    OrderFilters,
    OrderPeriodAggregate,
    OrdersRepository,
)
from app.schemas.orders import (
    OrderChartsResponse,
    OrderExceptionsPoint,
    OrderFulfillmentStatusPoint,
    OrderKpiResponse,
    OrderSalesChannelPoint,
    OrderStatusDistributionPoint,
    OrderTrendPoint,
)
from app.services.sales_channel_service import (
    SALES_CHANNEL_PRESENTATION,
    categorize_sales_channel,
)


FULFILLED_STATUSES = {"FULFILLED"}
PARTIALLY_FULFILLED_STATUSES = {"PARTIAL", "PARTIALLY_FULFILLED"}
UNFULFILLED_STATUSES = {"UNFULFILLED"}
SUPPORTED_ORDER_STATUSES = {"open", "cancelled"}
SALES_CHANNEL_NAMES = dict(SALES_CHANNEL_PRESENTATION)


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

    def get_charts(
        self, filters: OrderFilters = OrderFilters()
    ) -> OrderChartsResponse:
        bounds = self.repository.get_chart_date_bounds(filters)
        first_date = filters.start_date or bounds.first_date
        last_date = filters.end_date or bounds.last_date
        granularity = self._chart_granularity(first_date, last_date)
        period_rows = self.repository.get_period_aggregates(filters, granularity)
        periods = self._fill_periods(
            period_rows, first_date, last_date, granularity
        )
        kpi_aggregates = self.repository.get_kpi_aggregates(filters)

        fulfillment_counts = {
            "Fulfilled": 0,
            "Unfulfilled": 0,
            "Partially Fulfilled": 0,
        }
        for row in kpi_aggregates:
            status = self._normalize_status(row.fulfillment_status)
            if status in FULFILLED_STATUSES:
                fulfillment_counts["Fulfilled"] += row.orders_count or 0
            elif status in UNFULFILLED_STATUSES:
                fulfillment_counts["Unfulfilled"] += row.orders_count or 0
            elif status in PARTIALLY_FULFILLED_STATUSES:
                fulfillment_counts["Partially Fulfilled"] += row.orders_count or 0

        return OrderChartsResponse(
            granularity=granularity,
            orders_trend=[
                OrderTrendPoint(date=row.date, orders=row.orders) for row in periods
            ],
            fulfillment_status=[
                OrderFulfillmentStatusPoint(status=status, orders=count)
                for status, count in fulfillment_counts.items()
            ],
            orders_by_sales_channel=self._sales_channel_points(filters),
            order_status_distribution=self._status_distribution_points(filters),
            order_exceptions_trend=[
                OrderExceptionsPoint(
                    date=row.date,
                    cancelled_orders=row.cancelled_orders,
                    refunded_orders=row.refunded_orders,
                )
                for row in periods
            ],
        )

    def _status_distribution_points(
        self, filters: OrderFilters
    ) -> list[OrderStatusDistributionPoint]:
        counts = {
            "Fulfilled": 0,
            "Unfulfilled": 0,
            "Cancelled": 0,
            "Refunded": 0,
        }
        for row in self.repository.get_status_distribution(filters):
            if row.value in counts:
                counts[row.value] += row.orders or 0
        return [
            OrderStatusDistributionPoint(status=status, orders=orders)
            for status, orders in counts.items()
        ]

    def _sales_channel_points(
        self, filters: OrderFilters
    ) -> list[OrderSalesChannelPoint]:
        grouped: dict[str, int] = {}
        for row in self.repository.get_sales_channel_aggregates(filters):
            source = (row.value or "").strip()
            label = (
                SALES_CHANNEL_NAMES[categorize_sales_channel(source)]
                if source
                else "Unknown"
            )
            grouped[label] = grouped.get(label, 0) + (row.orders or 0)
        return [
            OrderSalesChannelPoint(sales_channel=label, orders=orders)
            for label, orders in sorted(
                grouped.items(), key=lambda item: (-item[1], item[0].lower())
            )
        ]

    @staticmethod
    def _chart_granularity(
        first_date: date | None, last_date: date | None
    ) -> str:
        return "week"

    @classmethod
    def _fill_periods(
        cls,
        rows: list[OrderPeriodAggregate],
        first_date: date | None,
        last_date: date | None,
        granularity: str,
    ) -> list[OrderPeriodAggregate]:
        if not first_date or not last_date:
            return rows
        current = cls._period_start(first_date, granularity)
        end = cls._period_start(last_date, granularity)
        by_date = {row.date: row for row in rows}
        filled: list[OrderPeriodAggregate] = []
        while current <= end:
            filled.append(
                by_date.get(current, OrderPeriodAggregate(current, 0, 0, 0))
            )
            current = cls._next_period(current, granularity)
        return filled

    @staticmethod
    def _period_start(value: date, granularity: str) -> date:
        if granularity == "week":
            return value - timedelta(days=value.weekday())
        if granularity == "month":
            return value.replace(day=1)
        return value

    @staticmethod
    def _next_period(value: date, granularity: str) -> date:
        if granularity == "week":
            return value + timedelta(days=7)
        if granularity == "month":
            return value + timedelta(days=monthrange(value.year, value.month)[1])
        return value + timedelta(days=1)

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        return "_".join((status or "").strip().upper().replace("-", " ").split())
