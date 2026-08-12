from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import Integer, case, cast, func, literal, select
from sqlalchemy.dialects.postgresql import JSONPATH
from sqlalchemy.orm import Session

from app.db.models import (
    InventoryLevel,
    Location,
    Order,
    OrderLineItem,
    Product,
    ProductVariant,
)


@dataclass(frozen=True)
class InventoryKpiInputs:
    total_inventory_units: int
    in_stock_products: int
    low_stock_products: int
    out_of_stock_products: int
    units_sold: int


@dataclass(frozen=True)
class InventoryTableRow:
    variant_id: str
    location_id: str | None
    product_title: str | None
    variant_title: str | None
    inventory_units: int | None
    location_name: str | None
    inventory_location_name: str | None
    inventory_tracked: bool | None


@dataclass(frozen=True)
class InventoryTableResult:
    rows: list[InventoryTableRow]
    total_items: int
    total_inventory_units: int = 0


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

    def get_inventory_table(
        self,
        page: int,
        page_size: int,
        sort_order: str = "asc",
    ) -> InventoryTableResult:
        base_statement = self._inventory_table_base_statement()
        total_items = self.db.scalar(
            select(func.count()).select_from(base_statement.subquery())
        ) or 0
        total_inventory_units = self.db.scalar(
            self._total_inventory_units_statement()
        ) or 0
        statement = self._inventory_table_statement(page, page_size, sort_order)
        rows = [InventoryTableRow(*row) for row in self.db.execute(statement).all()]
        return InventoryTableResult(
            rows=rows,
            total_items=total_items,
            total_inventory_units=total_inventory_units,
        )

    def get_inventory_table_export(
        self,
        sort_order: str = "asc",
    ) -> list[InventoryTableRow]:
        statement = self._inventory_table_ordered_statement(sort_order)
        return [InventoryTableRow(*row) for row in self.db.execute(statement).all()]

    @classmethod
    def _inventory_table_statement(
        cls,
        page: int,
        page_size: int,
        sort_order: str,
    ):
        statement = cls._inventory_table_ordered_statement(sort_order)
        return statement.offset((page - 1) * page_size).limit(page_size)

    @classmethod
    def _inventory_table_ordered_statement(cls, sort_order: str):
        statement = cls._inventory_table_base_statement()
        inventory_units = statement.selected_columns.inventory_units
        inventory_order = (
            inventory_units.desc().nulls_last()
            if sort_order == "desc"
            else inventory_units.asc().nulls_last()
        )
        return statement.order_by(
            inventory_order,
            func.lower(Product.title).asc().nulls_last(),
            func.lower(ProductVariant.title).asc().nulls_last(),
            func.lower(
                func.coalesce(Location.name, InventoryLevel.location_name)
            ).asc().nulls_last(),
            ProductVariant.id.asc(),
            InventoryLevel.location_id.asc().nulls_last(),
        )

    @staticmethod
    def _inventory_table_base_statement():
        available_quantity = cast(
            func.jsonb_path_query_first(
                InventoryLevel.quantities,
                cast(
                    literal('$[*] ? (@.name == "available").quantity'),
                    JSONPATH,
                ),
            ),
            Integer,
        ).label("inventory_units")
        return (
            select(
                ProductVariant.id.label("variant_id"),
                InventoryLevel.location_id,
                Product.title.label("product_title"),
                ProductVariant.title.label("variant_title"),
                available_quantity,
                Location.name.label("location_name"),
                InventoryLevel.location_name.label("inventory_location_name"),
                ProductVariant.inventory_tracked,
            )
            .select_from(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id, isouter=True)
            .join(
                InventoryLevel,
                InventoryLevel.inventory_item_id == ProductVariant.inventory_item_id,
                isouter=True,
            )
            .join(Location, Location.id == InventoryLevel.location_id, isouter=True)
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

    @classmethod
    def _total_inventory_units_statement(cls):
        products = cls._product_inventory_statement().subquery()
        return select(
            func.coalesce(func.sum(products.c.inventory_units), 0)
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
