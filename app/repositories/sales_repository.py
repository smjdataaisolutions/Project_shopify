from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Date, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderLineItem


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


@dataclass(frozen=True)
class SalesActionExportRow:
    order_id: str
    product_name: str | None
    financial_status: str | None
    amount_refunded: Decimal | None
    refund_reason: str | None
    cancelled_at: datetime | None
    refunded_date: datetime | None


class SalesRepository:
    """Database queries for sales analytics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_sales_metrics(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> SalesMetrics:
        """Return SAL-001-compatible aggregates for an optional processed period."""
        statement = self._with_date_filters(
            self._sales_metrics_statement(), start_date, end_date
        )
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
        )

    @staticmethod
    def _sales_metrics_statement():
        return select(
            func.sum(Order.subtotal_price).label("gross_sales"),
            func.sum(Order.total_discount).label("discounts"),
            func.sum(
                func.coalesce(Order.subtotal_price, 0)
                - func.coalesce(Order.total_discount, 0)
            ).label("net_sales"),
            func.sum(Order.total_shipping).label("shipping"),
            func.sum(Order.total_tax).label("taxes"),
            func.sum(Order.total_price).label("total_sales"),
            func.count().label("orders_count"),
            (
                func.sum(Order.total_price) / func.nullif(func.count(), 0)
            ).label("average_order_value"),
            func.max(Order.currency_code).label("currency_code"),
            func.count(func.distinct(Order.currency_code)).label("currency_count"),
            func.count()
            .filter(Order.financial_status.in_(("REFUNDED", "PARTIALLY_REFUNDED")))
            .label("refunded_orders"),
            func.count()
            .filter(Order.cancelled_at.is_not(None))
            .label("cancelled_orders"),
        )

    def get_revenue_trend(
        self,
        start_date: date | None,
        end_date: date | None,
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

        statement = self._with_date_filters(statement, start_date, end_date)

        return list(self.db.execute(statement).all())

    def get_action_export_rows(
        self,
        start_date: date | None,
        end_date: date | None,
    ) -> list[SalesActionExportRow]:
        """Return order and product rows contributing to the refund/cancel rule."""
        statement = self._with_date_filters(
            self._action_export_statement(), start_date, end_date
        )

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
