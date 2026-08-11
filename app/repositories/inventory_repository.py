from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderLineItem, ProductVariant


@dataclass(frozen=True)
class InventoryKpiInputs:
    total_inventory_units: int
    in_stock_products: int
    low_stock_products: int
    out_of_stock_products: int
    units_sold: int


class InventoryRepository:
    """PostgreSQL aggregates used to calculate Inventory KPIs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_kpi_inputs(
        self,
        start_date: date,
        end_date: date,
        low_stock_threshold: int,
    ) -> InventoryKpiInputs:
        inventory_row = self.db.execute(
            self._inventory_metrics_statement(low_stock_threshold)
        ).one()
        units_sold = self.db.scalar(
            self._units_sold_statement(start_date, end_date)
        ) or 0

        return InventoryKpiInputs(
            total_inventory_units=inventory_row.total_inventory_units or 0,
            in_stock_products=inventory_row.in_stock_products or 0,
            low_stock_products=inventory_row.low_stock_products or 0,
            out_of_stock_products=inventory_row.out_of_stock_products or 0,
            units_sold=units_sold,
        )

    @classmethod
    def _inventory_metrics_statement(cls, low_stock_threshold: int):
        products = cls._product_inventory_statement().subquery()
        return select(
            func.coalesce(func.sum(products.c.inventory_units), 0).label(
                "total_inventory_units"
            ),
            func.count()
            .filter(products.c.inventory_units > 0)
            .label("in_stock_products"),
            func.count()
            .filter(products.c.inventory_units.between(1, low_stock_threshold))
            .label("low_stock_products"),
            func.count()
            .filter(products.c.inventory_units == 0)
            .label("out_of_stock_products"),
        ).select_from(products)

    @staticmethod
    def _product_inventory_statement():
        """Aggregate Shopify's shop-wide variant availability once per product."""
        return (
            select(
                ProductVariant.product_id,
                func.greatest(
                    func.sum(ProductVariant.inventory_quantity),
                    0,
                ).label("inventory_units"),
            )
            .where(
                ProductVariant.product_id.is_not(None),
                ProductVariant.inventory_tracked.is_(True),
                ProductVariant.inventory_quantity.is_not(None),
            )
            .group_by(ProductVariant.product_id)
        )

    @staticmethod
    def _units_sold_statement(start_date: date, end_date: date):
        return (
            select(func.coalesce(func.sum(OrderLineItem.quantity), 0))
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
            .where(
                OrderLineItem.quantity > 0,
                Order.processed_at >= start_date,
                Order.processed_at < end_date + timedelta(days=1),
            )
        )
