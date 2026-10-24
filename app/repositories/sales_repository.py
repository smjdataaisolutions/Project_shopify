from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Date, case, func, or_, select
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


@dataclass(frozen=True)
class SalesChartAggregateRow:
    id: str
    label: date | str
    revenue: Decimal
    orders: int
    units_sold: int


@dataclass(frozen=True)
class SalesChartResult:
    rows: list[SalesChartAggregateRow]
    currency_code: str | None
    total_revenue: Decimal = Decimal("0")
    total_orders: int = 0
    total_units_sold: int = 0


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
        period = func.timezone("UTC", Order.processed_at).cast(Date).label("period")
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

    def get_sales_chart(
        self,
        filters: SalesFilters,
        dimension: str,
        measure: str,
        product_ids: tuple[str, ...] | None = None,
    ) -> SalesChartResult:
        """Aggregate an allowlisted Sales Explorer selection in PostgreSQL."""
        statement = (
            self._product_chart_statement(filters, measure, product_ids)
            if dimension == "product"
            else self._order_chart_statement(filters, dimension)
        )
        rows = [SalesChartAggregateRow(*row) for row in self.db.execute(statement)]
        totals = self.db.execute(self._chart_totals_statement(filters)).one()
        return SalesChartResult(
            rows=rows,
            currency_code=(
                totals.currency_code
                if totals.currency_count == 1
                else None
            ),
            total_revenue=totals.revenue or Decimal("0"),
            total_orders=totals.orders or 0,
            total_units_sold=totals.units_sold or 0,
        )

    def _chart_totals_statement(self, filters: SalesFilters):
        units_by_order = (
            select(
                OrderLineItem.order_id.label("order_id"),
                func.coalesce(func.sum(OrderLineItem.quantity), 0).label("units"),
            )
            .group_by(OrderLineItem.order_id)
            .subquery()
        )
        statement = (
            select(
                func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
                func.count(func.distinct(Order.id)).label("orders"),
                func.coalesce(func.sum(units_by_order.c.units), 0).label(
                    "units_sold"
                ),
                func.max(Order.currency_code).label("currency_code"),
                func.count(func.distinct(Order.currency_code)).label(
                    "currency_count"
                ),
            )
            .select_from(Order)
            .outerjoin(units_by_order, units_by_order.c.order_id == Order.id)
            .where(Order.processed_at.is_not(None))
        )
        return self._apply_filters(statement, filters)

    def _order_chart_statement(self, filters: SalesFilters, dimension: str):
        units_by_order = (
            select(
                OrderLineItem.order_id.label("order_id"),
                func.coalesce(func.sum(OrderLineItem.quantity), 0).label("units"),
            )
            .group_by(OrderLineItem.order_id)
            .subquery()
        )
        if dimension == "processed_date":
            group_value = func.timezone("UTC", Order.processed_at).cast(Date)
            identifier = group_value
            label = group_value
        else:
            group_value = func.coalesce(func.nullif(func.btrim(Order.sales_channel), ""), "unknown")
            identifier = group_value
            label = group_value

        statement = (
            select(
                identifier.label("id"),
                label.label("label"),
                func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
                func.count(func.distinct(Order.id)).label("orders"),
                func.coalesce(func.sum(units_by_order.c.units), 0).label(
                    "units_sold"
                ),
            )
            .select_from(Order)
            .outerjoin(units_by_order, units_by_order.c.order_id == Order.id)
            .where(Order.processed_at.is_not(None))
            .group_by(group_value)
        )
        statement = self._apply_filters(statement, filters)
        return (
            statement.order_by(group_value.asc())
            if dimension == "processed_date"
            else statement.order_by(func.sum(Order.total_price).desc(), group_value.asc())
        )

    def _product_chart_statement(
        self,
        filters: SalesFilters,
        measure: str,
        product_ids: tuple[str, ...] | None = None,
    ):
        line_value = (
            func.coalesce(OrderLineItem.unit_price, 0)
            * func.coalesce(OrderLineItem.quantity, 0)
        )
        order_line_totals = (
            select(
                OrderLineItem.order_id.label("order_id"),
                func.sum(line_value).label("order_line_value"),
            )
            .group_by(OrderLineItem.order_id)
            .subquery()
        )
        product_key = func.coalesce(
            OrderLineItem.product_id,
            func.concat(
                "unknown:",
                func.lower(
                    func.coalesce(func.btrim(OrderLineItem.title), "unknown")
                ),
            ),
        )
        product_by_order = (
            select(
                OrderLineItem.order_id.label("order_id"),
                product_key.label("product_id"),
                func.coalesce(func.max(OrderLineItem.title), "Unknown product").label(
                    "product_name"
                ),
                func.sum(line_value).label("product_line_value"),
                func.coalesce(func.sum(OrderLineItem.quantity), 0).label("units"),
            )
            .where(OrderLineItem.order_id.is_not(None))
            .group_by(
                OrderLineItem.order_id,
                product_key,
            )
            .subquery()
        )
        attributed_revenue = case(
            (
                order_line_totals.c.order_line_value > 0,
                func.coalesce(Order.total_price, 0)
                * product_by_order.c.product_line_value
                / order_line_totals.c.order_line_value,
            ),
            else_=0,
        )
        statement = (
            select(
                product_by_order.c.product_id.label("id"),
                func.max(product_by_order.c.product_name).label("label"),
                func.coalesce(func.sum(attributed_revenue), 0).label("revenue"),
                func.count(func.distinct(Order.id)).label("orders"),
                func.coalesce(func.sum(product_by_order.c.units), 0).label(
                    "units_sold"
                ),
            )
            .select_from(product_by_order)
            .join(Order, Order.id == product_by_order.c.order_id)
            .join(order_line_totals, order_line_totals.c.order_id == Order.id)
            .where(Order.processed_at.is_not(None))
            .group_by(product_by_order.c.product_id)
        )
        statement = self._apply_filters(statement, filters)
        if product_ids is not None:
            statement = statement.where(
                product_by_order.c.product_id.in_(product_ids)
            )
        ordering = {
            "revenue": func.sum(attributed_revenue),
            "orders": func.count(func.distinct(Order.id)),
            "units_sold": func.sum(product_by_order.c.units),
        }[measure]
        statement = statement.order_by(
            ordering.desc(), product_by_order.c.product_id.asc()
        )
        return statement if product_ids is not None else statement.limit(5)

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
