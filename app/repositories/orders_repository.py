from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderLineItem


@dataclass(frozen=True)
class OrderFilters:
    start_date: date | None = None
    end_date: date | None = None
    sales_channels: tuple[str, ...] = ()
    order_statuses: tuple[str, ...] = ()
    fulfillment_statuses: tuple[str, ...] = ()
    payment_statuses: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrderKpiAggregate:
    fulfillment_status: str | None
    orders_count: int
    units_ordered: int
    cancelled_orders: int
    refunded_orders: int


class OrdersRepository:
    """PostgreSQL queries for Orders analytics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_kpi_aggregates(
        self, filters: OrderFilters = OrderFilters()
    ) -> list[OrderKpiAggregate]:
        """Return one aggregate row per raw Shopify fulfillment status."""
        statement = self._apply_filters(self._kpi_statement(), filters)
        return [OrderKpiAggregate(*row) for row in self.db.execute(statement)]

    @staticmethod
    def _kpi_statement():
        units_by_order = (
            select(
                OrderLineItem.order_id.label("order_id"),
                func.coalesce(func.sum(OrderLineItem.quantity), 0).label("units"),
            )
            .where(OrderLineItem.order_id.is_not(None))
            .group_by(OrderLineItem.order_id)
            .subquery()
        )
        normalized_financial_status = func.upper(
            func.btrim(Order.financial_status)
        )
        has_refund_activity = or_(
            Order.refunded_at.is_not(None),
            Order.total_refunded > 0,
            normalized_financial_status.in_(("REFUNDED", "PARTIALLY_REFUNDED")),
        )

        return (
            select(
                Order.fulfillment_status.label("fulfillment_status"),
                func.count(func.distinct(Order.id)).label("orders_count"),
                func.coalesce(func.sum(units_by_order.c.units), 0).label(
                    "units_ordered"
                ),
                func.count(
                    func.distinct(
                        case((Order.cancelled_at.is_not(None), Order.id))
                    )
                ).label("cancelled_orders"),
                func.count(
                    func.distinct(case((has_refund_activity, Order.id)))
                ).label("refunded_orders"),
            )
            .select_from(Order)
            .outerjoin(units_by_order, units_by_order.c.order_id == Order.id)
            .where(Order.processed_at.is_not(None))
            .group_by(Order.fulfillment_status)
        )

    @staticmethod
    def _apply_filters(statement, filters: OrderFilters):
        if filters.start_date:
            statement = statement.where(Order.processed_at >= filters.start_date)
        if filters.end_date:
            statement = statement.where(
                Order.processed_at < filters.end_date + timedelta(days=1)
            )
        if filters.sales_channels:
            statement = statement.where(
                Order.sales_channel.in_(filters.sales_channels)
            )
        if filters.order_statuses == ("open",):
            statement = statement.where(Order.cancelled_at.is_(None))
        elif filters.order_statuses == ("cancelled",):
            statement = statement.where(Order.cancelled_at.is_not(None))
        if filters.fulfillment_statuses:
            statement = statement.where(
                Order.fulfillment_status.in_(filters.fulfillment_statuses)
            )
        if filters.payment_statuses:
            statement = statement.where(
                Order.financial_status.in_(filters.payment_statuses)
            )
        return statement
