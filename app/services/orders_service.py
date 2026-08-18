from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import re

from app.repositories.orders_repository import (
    OrderFilters,
    OrderPeriodAggregate,
    OrderPerformanceRow,
    OrderTimelineRow,
    OrdersRepository,
)
from app.schemas.orders import (
    OrderChartsResponse,
    OrderExceptionsPoint,
    OrderFulfillmentStatusPoint,
    OrderKpiResponse,
    OrderPerformanceItem,
    OrderPerformanceMeta,
    OrderPerformancePagination,
    OrderPerformanceResponse,
    OrderSalesChannelPoint,
    OrderStatusDistributionPoint,
    OrderTrendPoint,
    OrderTimelineCurrentStatus,
    OrderTimelineEvent,
    OrderTimelineResponse,
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
ATTENTION_FULFILLMENT_DAYS = 2
CRITICAL_FULFILLMENT_DAYS = 5


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

    def get_performance_insights(
        self,
        filters: OrderFilters,
        page: int,
        page_size: int,
        search: str,
        sort_by: str,
        sort_direction: str,
        current_time: datetime | None = None,
    ) -> OrderPerformanceResponse:
        current_time = current_time or datetime.now(timezone.utc)
        result = self.repository.get_performance_insights(
            filters,
            page,
            page_size,
            search.strip(),
            sort_by,
            sort_direction,
            current_time,
            ATTENTION_FULFILLMENT_DAYS * 86400,
            CRITICAL_FULFILLMENT_DAYS * 86400,
        )
        total_pages = (
            (result.total_items + page_size - 1) // page_size
            if result.total_items
            else 0
        )
        return OrderPerformanceResponse(
            items=[
                self._performance_item(row, current_time)
                for row in result.rows
            ],
            pagination=OrderPerformancePagination(
                page=page,
                page_size=page_size,
                total_items=result.total_items,
                total_pages=total_pages,
            ),
            meta=OrderPerformanceMeta(
                historical_fulfillment_time_supported=False,
                order_progress_age_supported=True,
                not_required_supported=False,
            ),
        )

    def get_timeline(self, order_id: str) -> OrderTimelineResponse | None:
        if not re.fullmatch(r"gid://shopify/Order/\d+", order_id):
            raise ValueError("Invalid Shopify order ID")
        row = self.repository.get_timeline(order_id)
        if row is None:
            return None
        events = self._timeline_events(row)
        order_name = (row.order_name or "").strip() or self._fallback_order_name(
            row.order_id
        )
        return OrderTimelineResponse(
            order_id=row.order_id,
            order_name=order_name,
            events=events,
            current_status=OrderTimelineCurrentStatus(
                payment_status=self._status_value(row.financial_status),
                fulfillment_status=self._status_value(row.fulfillment_status),
            ),
            currency=row.currency_code,
        )

    @classmethod
    def _timeline_events(cls, row: OrderTimelineRow) -> list[OrderTimelineEvent]:
        events: list[OrderTimelineEvent] = []
        if row.created_at is not None:
            events.append(
                OrderTimelineEvent(
                    event_type="order_created",
                    title="Order created",
                    occurred_at=row.created_at,
                    description=None,
                    amount=None,
                )
            )
        if row.processed_at is not None:
            events.append(
                OrderTimelineEvent(
                    event_type="order_processed",
                    title="Order processed",
                    occurred_at=row.processed_at,
                    description=None,
                    amount=None,
                )
            )
        if row.cancelled_at is not None:
            events.append(
                OrderTimelineEvent(
                    event_type="order_cancelled",
                    title="Order cancelled",
                    occurred_at=row.cancelled_at,
                    description=None,
                    amount=None,
                )
            )
        if row.refunded_at is not None:
            refund_amount = Decimal(row.total_refunded or 0)
            events.append(
                OrderTimelineEvent(
                    event_type="refund_recorded",
                    title="Refund recorded",
                    occurred_at=row.refunded_at,
                    description=(row.refund_reason or "").strip() or None,
                    amount=float(refund_amount),
                )
            )
        return sorted(events, key=lambda event: event.occurred_at)

    @classmethod
    def _status_value(cls, status: str | None) -> str | None:
        normalized = cls._normalize_status(status)
        return normalized.lower() if normalized else None

    @classmethod
    def _performance_item(
        cls,
        row: OrderPerformanceRow,
        current_time: datetime,
    ) -> OrderPerformanceItem:
        progress, progress_seconds, progress_label = cls._order_progress(
            row, current_time
        )
        fulfillment_status = cls._effective_fulfillment_status(row)
        health, reason = cls._fulfillment_health(
            fulfillment_status, progress_seconds
        )
        order_name = (row.order_name or "").strip() or cls._fallback_order_name(
            row.order_id
        )
        return OrderPerformanceItem(
            order_id=row.order_id,
            order_name=order_name,
            order_date=row.order_date,
            units_ordered=row.units_ordered or 0,
            fulfillment_status=fulfillment_status,
            order_progress=progress,
            order_progress_seconds=progress_seconds,
            order_progress_label=progress_label,
            fulfillment_health=health,
            fulfillment_health_reason=reason,
            shopify_admin_url=cls._shopify_admin_url(row.order_id),
        )

    @classmethod
    def _fulfillment_health(
        cls,
        fulfillment_status: str,
        progress_seconds: int | None,
    ) -> tuple[str, str | None]:
        if fulfillment_status == "cancelled":
            return "cancelled", "Order is cancelled"
        if fulfillment_status == "unknown":
            return "unknown", "Fulfilment status is unavailable"
        if (
            fulfillment_status in {"unfulfilled", "partially_fulfilled"}
            and progress_seconds is not None
            and progress_seconds > CRITICAL_FULFILLMENT_DAYS * 86400
        ):
            label = cls._fulfillment_status_label(fulfillment_status)
            return (
                "critical",
                f"{label} for more than {CRITICAL_FULFILLMENT_DAYS} days",
            )
        if fulfillment_status == "partially_fulfilled":
            return "attention_needed", "Order is partially fulfilled"
        if (
            fulfillment_status == "unfulfilled"
            and progress_seconds is not None
            and progress_seconds > ATTENTION_FULFILLMENT_DAYS * 86400
        ):
            return (
                "attention_needed",
                f"Unfulfilled for more than {ATTENTION_FULFILLMENT_DAYS} days",
            )
        return "healthy", None

    @classmethod
    def _effective_fulfillment_status(cls, row: OrderPerformanceRow) -> str:
        if row.cancelled_at is not None:
            return "cancelled"
        status = cls._normalize_status(row.fulfillment_status)
        if status in FULFILLED_STATUSES:
            return "fulfilled"
        if status in PARTIALLY_FULFILLED_STATUSES:
            return "partially_fulfilled"
        if status in UNFULFILLED_STATUSES:
            return "unfulfilled"
        return "unknown"

    @staticmethod
    def _fulfillment_status_label(status: str) -> str:
        return (
            "Partially fulfilled"
            if status == "partially_fulfilled"
            else "Unfulfilled"
        )

    @classmethod
    def _order_progress(
        cls, row: OrderPerformanceRow, current_time: datetime
    ) -> tuple[str, int | None, str]:
        if row.cancelled_at is not None:
            return "cancelled", None, "Cancelled"
        status = cls._normalize_status(row.fulfillment_status)
        if status in FULFILLED_STATUSES:
            return "fulfilled", None, "Fulfilled"
        if status in PARTIALLY_FULFILLED_STATUSES:
            seconds = cls._open_duration_seconds(row.order_date, current_time)
            return (
                "in_progress",
                seconds,
                f"In progress for {cls._duration_label(seconds)}",
            )
        if status in UNFULFILLED_STATUSES:
            seconds = cls._open_duration_seconds(row.order_date, current_time)
            return "open", seconds, f"Open for {cls._duration_label(seconds)}"
        return "unknown", None, "Unknown"

    @staticmethod
    def _open_duration_seconds(order_date: datetime, current_time: datetime) -> int:
        if order_date.tzinfo is None:
            order_date = order_date.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        return max(0, int((current_time - order_date).total_seconds()))

    @staticmethod
    def _duration_label(seconds: int) -> str:
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        if days:
            label = f"{days} day" if days == 1 else f"{days} days"
            if hours:
                label += f" {hours} hour" if hours == 1 else f" {hours} hours"
            return label
        if hours:
            return f"{hours} hour" if hours == 1 else f"{hours} hours"
        if minutes:
            return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
        return "less than 1 minute"

    @staticmethod
    def _shopify_admin_url(order_id: str) -> str | None:
        match = re.fullmatch(r"gid://shopify/Order/(\d+)", order_id)
        return f"shopify://admin/orders/{match.group(1)}" if match else None

    @staticmethod
    def _fallback_order_name(order_id: str) -> str:
        match = re.search(r"/(\d+)$", order_id)
        return f"Order {match.group(1)}" if match else "Order"

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
