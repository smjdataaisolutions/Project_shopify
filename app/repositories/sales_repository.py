from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Date, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderLineItem, ShopifySyncState


@dataclass(frozen=True)
class SalesMetrics:
    gross_sales: Decimal | None
    discounts: Decimal | None
    net_sales: Decimal | None
    shipping: Decimal | None
    taxes: Decimal | None
    total_sales: Decimal | None
    orders_count: int | None
    average_order_value: Decimal | None
    currency_code: str | None
    currency_count: int
    refunded_orders: int | None = 0
    cancelled_orders: int | None = 0
    returns_refunds: Decimal | None = 0
    last_updated_at: datetime | None = None


@dataclass(frozen=True)
class DailySalesBreakdownRow:
    date: date
    gross_sales: Decimal
    discounts: Decimal
    returns_refunds: Decimal
    net_sales: Decimal
    shipping: Decimal
    tax: Decimal
    total_sales: Decimal
    orders: int


@dataclass(frozen=True)
class DailySalesBreakdownResult:
    rows: list[DailySalesBreakdownRow]
    total_items: int
    gross_sales: Decimal
    discounts: Decimal
    returns_refunds: Decimal
    net_sales: Decimal
    shipping: Decimal
    tax: Decimal
    total_sales: Decimal
    orders: int
    currency_code: str | None


@dataclass(frozen=True)
class SalesActionExportRow:
    order_id: str
    product_name: str | None
    financial_status: str | None
    amount_refunded: Decimal | None
    refund_reason: str | None
    cancelled_at: datetime | None
    refunded_date: datetime | None


@dataclass(frozen=True)
class SalesFilters:
    start_date: date | None = None
    end_date: date | None = None
    sales_channels: tuple[str, ...] = ()
    financial_statuses: tuple[str, ...] = ()
    currency_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SalesFilterOptions:
    sales_channels: tuple[str, ...]
    financial_statuses: tuple[str, ...]
    currency_codes: tuple[str, ...]


class SalesRepository:
    """Database queries for sales analytics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_sales_metrics(
        self,
        filters: SalesFilters = SalesFilters(),
    ) -> SalesMetrics:
        """Return SAL-001-compatible aggregates for an optional processed period."""
        statement = self._apply_filters(self._sales_metrics_statement(), filters)
        row = self.db.execute(statement).one()
        return SalesMetrics(
            gross_sales=row.gross_sales,
            discounts=row.discounts,
            net_sales=row.net_sales,
            shipping=row.shipping,
            taxes=row.taxes,
            total_sales=row.total_sales,
            orders_count=row.orders_count,
            average_order_value=row.average_order_value,
            currency_code=row.currency_code,
            currency_count=row.currency_count,
            refunded_orders=row.refunded_orders,
            cancelled_orders=row.cancelled_orders,
            returns_refunds=row.returns_refunds,
            last_updated_at=row.last_updated_at,
        )

    def get_filter_options(self) -> SalesFilterOptions:
        """Return exact non-empty order dimensions stored in PostgreSQL."""
        return SalesFilterOptions(
            sales_channels=self._distinct_non_empty(Order.sales_channel),
            financial_statuses=self._distinct_non_empty(Order.financial_status),
            currency_codes=self._distinct_non_empty(Order.currency_code),
        )

    def get_daily_breakdown(
        self,
        filters: SalesFilters,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
    ) -> DailySalesBreakdownResult:
        """Return paginated daily metrics and totals from the shared KPI fields."""
        daily = self._daily_breakdown_statement(filters).subquery()
        summary = self.db.execute(
            select(
                func.count().label("total_items"),
                func.coalesce(func.sum(daily.c.gross_sales), 0).label("gross_sales"),
                func.coalesce(func.sum(daily.c.discounts), 0).label("discounts"),
                func.coalesce(func.sum(daily.c.returns_refunds), 0).label(
                    "returns_refunds"
                ),
                func.coalesce(func.sum(daily.c.net_sales), 0).label("net_sales"),
                func.coalesce(func.sum(daily.c.shipping), 0).label("shipping"),
                func.coalesce(func.sum(daily.c.tax), 0).label("tax"),
                func.coalesce(func.sum(daily.c.total_sales), 0).label("total_sales"),
                func.coalesce(func.sum(daily.c.orders), 0).label("orders"),
                func.max(daily.c.currency_code).label("currency_code"),
                func.count(func.distinct(daily.c.currency_code)).label(
                    "currency_count"
                ),
                func.coalesce(func.max(daily.c.currency_count), 0).label(
                    "max_daily_currency_count"
                ),
            ).select_from(daily)
        ).one()
        statement = self._daily_breakdown_page_statement(
            daily, page, page_size, sort_by, sort_direction
        )
        return DailySalesBreakdownResult(
            rows=[DailySalesBreakdownRow(*row) for row in self.db.execute(statement)],
            total_items=summary.total_items or 0,
            gross_sales=summary.gross_sales or Decimal("0"),
            discounts=summary.discounts or Decimal("0"),
            returns_refunds=summary.returns_refunds or Decimal("0"),
            net_sales=summary.net_sales or Decimal("0"),
            shipping=summary.shipping or Decimal("0"),
            tax=summary.tax or Decimal("0"),
            total_sales=summary.total_sales or Decimal("0"),
            orders=summary.orders or 0,
            currency_code=(
                summary.currency_code
                if summary.currency_count == 1
                and summary.max_daily_currency_count == 1
                else None
            ),
        )

    @staticmethod
    def _sales_metrics_statement():
        return select(
            func.sum(Order.subtotal_price).label("gross_sales"),
            func.sum(Order.total_discount).label("discounts"),
            func.sum(Order.total_refunded).label("returns_refunds"),
            func.sum(
                func.coalesce(Order.subtotal_price, 0)
                - func.coalesce(Order.total_discount, 0)
                - func.coalesce(Order.total_refunded, 0)
            ).label("net_sales"),
            func.sum(Order.total_shipping).label("shipping"),
            func.sum(Order.total_tax).label("taxes"),
            func.sum(Order.total_price).label("total_sales"),
            func.count(func.distinct(Order.id)).label("orders_count"),
            (
                func.sum(Order.total_price)
                / func.nullif(func.count(func.distinct(Order.id)), 0)
            ).label("average_order_value"),
            func.max(Order.currency_code).label("currency_code"),
            func.count(func.distinct(Order.currency_code)).label("currency_count"),
            func.count()
            .filter(Order.financial_status.in_(("REFUNDED", "PARTIALLY_REFUNDED")))
            .label("refunded_orders"),
            func.count()
            .filter(Order.cancelled_at.is_not(None))
            .label("cancelled_orders"),
            select(ShopifySyncState.last_successful_sync_at)
            .where(ShopifySyncState.source == "shopify")
            .scalar_subquery()
            .label("last_updated_at"),
        ).where(Order.processed_at.is_not(None))

    def _daily_breakdown_statement(self, filters: SalesFilters):
        processed_date = func.timezone("UTC", Order.processed_at).cast(Date)
        statement = (
            select(
                processed_date.label("date"),
                func.coalesce(func.sum(Order.subtotal_price), 0).label(
                    "gross_sales"
                ),
                func.coalesce(func.sum(Order.total_discount), 0).label("discounts"),
                func.coalesce(func.sum(Order.total_refunded), 0).label(
                    "returns_refunds"
                ),
                func.coalesce(
                    func.sum(
                        func.coalesce(Order.subtotal_price, 0)
                        - func.coalesce(Order.total_discount, 0)
                        - func.coalesce(Order.total_refunded, 0)
                    ),
                    0,
                ).label("net_sales"),
                func.coalesce(func.sum(Order.total_shipping), 0).label("shipping"),
                func.coalesce(func.sum(Order.total_tax), 0).label("tax"),
                func.coalesce(func.sum(Order.total_price), 0).label("total_sales"),
                func.count(func.distinct(Order.id)).label("orders"),
                func.max(Order.currency_code).label("currency_code"),
                func.count(func.distinct(Order.currency_code)).label(
                    "currency_count"
                ),
            )
            .where(Order.processed_at.is_not(None))
            .group_by(processed_date)
        )
        return self._apply_filters(statement, filters)

    @staticmethod
    def _daily_breakdown_page_statement(
        daily, page: int, page_size: int, sort_by: str, sort_direction: str
    ):
        sort_columns = {
            "date": daily.c.date,
            "gross_sales": daily.c.gross_sales,
            "discounts": daily.c.discounts,
            "returns_refunds": daily.c.returns_refunds,
            "net_sales": daily.c.net_sales,
            "shipping": daily.c.shipping,
            "tax": daily.c.tax,
            "total_sales": daily.c.total_sales,
            "orders": daily.c.orders,
            "average_order_value": (
                daily.c.total_sales / func.nullif(daily.c.orders, 0)
            ),
        }
        column = sort_columns[sort_by]
        ordering = column.desc() if sort_direction == "desc" else column.asc()
        return (
            select(
                daily.c.date,
                daily.c.gross_sales,
                daily.c.discounts,
                daily.c.returns_refunds,
                daily.c.net_sales,
                daily.c.shipping,
                daily.c.tax,
                daily.c.total_sales,
                daily.c.orders,
            )
            .order_by(ordering, daily.c.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

    def get_revenue_trend(
        self,
        filters: SalesFilters,
    ) -> list[tuple[date, Decimal, str | None]]:
        """Return daily revenue aggregates ordered by the Shopify processed date."""
        period = func.date_trunc("day", Order.processed_at).cast(Date).label("period")
        statement = (
            select(
                period,
                func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
                func.max(Order.currency_code).label("currency"),
            )
            .where(Order.processed_at.is_not(None))
            .group_by(period)
            .order_by(period)
        )

        statement = self._apply_filters(statement, filters)

        return list(self.db.execute(statement).all())

    def get_action_export_rows(
        self,
        filters: SalesFilters,
    ) -> list[SalesActionExportRow]:
        """Return order and product rows contributing to the refund/cancel rule."""
        statement = self._apply_filters(self._action_export_statement(), filters)

        return [SalesActionExportRow(*row) for row in self.db.execute(statement).all()]

    @staticmethod
    def _action_export_statement():
        return (
            select(
                Order.id.label("order_id"),
                OrderLineItem.title.label("product_name"),
                Order.financial_status,
                Order.total_refunded.label("amount_refunded"),
                Order.refund_reason,
                Order.cancelled_at,
                Order.refunded_at.label("refunded_date"),
            )
            .select_from(Order)
            .outerjoin(OrderLineItem, OrderLineItem.order_id == Order.id)
            .where(
                or_(
                    Order.financial_status.in_(("REFUNDED", "PARTIALLY_REFUNDED")),
                    Order.cancelled_at.is_not(None),
                )
            )
            .order_by(Order.id.asc(), OrderLineItem.title.asc(), OrderLineItem.id.asc())
        )

    @staticmethod
    def _with_date_filters(statement, start_date: date | None, end_date: date | None):
        if start_date:
            statement = statement.where(Order.processed_at >= start_date)
        if end_date:
            statement = statement.where(Order.processed_at < end_date + timedelta(days=1))
        return statement

    @classmethod
    def _apply_filters(cls, statement, filters: SalesFilters):
        statement = cls._with_date_filters(
            statement, filters.start_date, filters.end_date
        )
        if filters.sales_channels:
            statement = statement.where(Order.sales_channel.in_(filters.sales_channels))
        if filters.financial_statuses:
            statement = statement.where(
                Order.financial_status.in_(filters.financial_statuses)
            )
        if filters.currency_codes:
            statement = statement.where(Order.currency_code.in_(filters.currency_codes))
        return statement

    def _distinct_non_empty(self, column) -> tuple[str, ...]:
        return tuple(
            self.db.scalars(
                select(column)
                .where(column.is_not(None), func.btrim(column) != "")
                .distinct()
                .order_by(column)
            ).all()
        )
