from dataclasses import dataclass
from datetime import date, datetime, timedelta

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


@dataclass(frozen=True)
class InventoryFilters:
    location_ids: tuple[str, ...] = ()
    vendors: tuple[str, ...] = ()
    inventory_tracked: bool | None = None
    inventory_statuses: tuple[str, ...] = ()


@dataclass(frozen=True)
class InventoryLocationOption:
    id: str
    name: str


@dataclass(frozen=True)
class InventoryFilterOptions:
    locations: list[InventoryLocationOption]
    vendors: list[str]
    latest_inventory_sync_at: datetime | None


class InventoryRepository:
    """PostgreSQL aggregates used to calculate Inventory KPIs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_kpi_inputs(
        self,
        start_date: date,
        end_date: date,
        low_stock_threshold: int,
        filters: InventoryFilters = InventoryFilters(),
    ) -> InventoryKpiInputs:
        inventory_row = self.db.execute(
            self._inventory_metrics_statement(low_stock_threshold, filters)
        ).one()
        units_sold = self.db.scalar(
            self._units_sold_statement(
                start_date,
                end_date,
                self._eligible_product_ids_statement(
                    filters,
                    low_stock_threshold,
                ) if _has_inventory_filters(filters) else None,
            )
        ) or 0

        return InventoryKpiInputs(
            total_inventory_units=inventory_row.total_inventory_units or 0,
            in_stock_products=inventory_row.in_stock_products or 0,
            low_stock_products=inventory_row.low_stock_products or 0,
            out_of_stock_products=inventory_row.out_of_stock_products or 0,
            units_sold=units_sold,
        )

    def get_filter_options(self) -> InventoryFilterOptions:
        location_rows = self.db.execute(
            select(Location.id, Location.name)
            .where(func.nullif(func.btrim(Location.name), "").is_not(None))
            .order_by(func.lower(func.btrim(Location.name)), Location.id)
        ).all()
        vendor_options = (
            select(func.btrim(Product.vendor).label("vendor"))
            .where(func.nullif(func.btrim(Product.vendor), "").is_not(None))
            .distinct()
            .subquery()
        )
        vendors = self.db.execute(
            select(vendor_options.c.vendor).order_by(
                func.lower(vendor_options.c.vendor)
            )
        ).scalars().all()
        return InventoryFilterOptions(
            locations=[
                InventoryLocationOption(id=row.id, name=row.name.strip())
                for row in location_rows
            ],
            vendors=list(vendors),
            latest_inventory_sync_at=self.db.scalar(
                select(func.max(InventoryLevel.updated_at))
            ),
        )

    def get_inventory_table(
        self,
        page: int,
        page_size: int,
        sort_order: str = "asc",
        filters: InventoryFilters = InventoryFilters(),
        low_stock_threshold: int = 10,
    ) -> InventoryTableResult:
        base_statement = self._inventory_table_base_statement(
            filters,
            low_stock_threshold,
        )
        total_items = self.db.scalar(
            select(func.count()).select_from(base_statement.subquery())
        ) or 0
        total_inventory_units = self.db.scalar(
            self._total_inventory_units_statement(
                filters,
                low_stock_threshold,
            )
        ) or 0
        statement = self._inventory_table_statement(
            page,
            page_size,
            sort_order,
            filters,
            low_stock_threshold,
        )
        rows = [
            InventoryTableRow(*row)
            for row in self.db.execute(statement).all()
        ]
        return InventoryTableResult(
            rows=rows,
            total_items=total_items,
            total_inventory_units=total_inventory_units,
        )

    def get_inventory_table_export(
        self,
        sort_order: str = "asc",
        filters: InventoryFilters = InventoryFilters(),
        low_stock_threshold: int = 10,
    ) -> list[InventoryTableRow]:
        statement = self._inventory_table_ordered_statement(
            sort_order,
            filters,
            low_stock_threshold,
        )
        return [
            InventoryTableRow(*row)
            for row in self.db.execute(statement).all()
        ]

    @classmethod
    def _inventory_table_statement(
        cls,
        page: int,
        page_size: int,
        sort_order: str,
        filters: InventoryFilters = InventoryFilters(),
        low_stock_threshold: int = 10,
    ):
        statement = cls._inventory_table_ordered_statement(
            sort_order,
            filters,
            low_stock_threshold,
        )
        return statement.offset((page - 1) * page_size).limit(page_size)

    @classmethod
    def _inventory_table_ordered_statement(
        cls,
        sort_order: str,
        filters: InventoryFilters = InventoryFilters(),
        low_stock_threshold: int = 10,
    ):
        statement = cls._inventory_table_base_statement(
            filters,
            low_stock_threshold,
        )
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

    @classmethod
    def _inventory_table_base_statement(
        cls,
        filters: InventoryFilters = InventoryFilters(),
        low_stock_threshold: int = 10,
    ):
        available_quantity = cls._available_quantity_expression().label(
            "inventory_units"
        )
        statement = (
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
                InventoryLevel.inventory_item_id
                == ProductVariant.inventory_item_id,
                isouter=True,
            )
            .join(
                Location,
                Location.id == InventoryLevel.location_id,
                isouter=True,
            )
        )
        return cls._apply_inventory_filters(
            statement,
            filters,
            available_quantity,
            low_stock_threshold,
        )

    @classmethod
    def _inventory_metrics_statement(
        cls,
        low_stock_threshold: int,
        filters: InventoryFilters = InventoryFilters(),
    ):
        inventory_items = cls._tracked_inventory_items_statement(
            filters,
            low_stock_threshold,
        ).subquery()
        return select(
            func.coalesce(
                func.sum(func.greatest(inventory_items.c.inventory_units, 0)),
                0,
            ).label(
                "total_inventory_units"
            ),
            func.count()
            .filter(inventory_items.c.inventory_units > 0)
            .label("in_stock_products"),
            func.count()
            .filter(
                inventory_items.c.inventory_units.between(
                    1,
                    low_stock_threshold,
                )
            )
            .label("low_stock_products"),
            func.count()
            .filter(inventory_items.c.inventory_units == 0)
            .label("out_of_stock_products"),
        ).select_from(inventory_items)

    @classmethod
    def _total_inventory_units_statement(
        cls,
        filters: InventoryFilters = InventoryFilters(),
        low_stock_threshold: int = 10,
    ):
        inventory_items = cls._tracked_inventory_items_statement(
            filters,
            low_stock_threshold,
        ).subquery()
        return select(
            func.coalesce(
                func.sum(func.greatest(inventory_items.c.inventory_units, 0)),
                0,
            )
        ).select_from(inventory_items)

    @classmethod
    def _tracked_inventory_items_statement(
        cls,
        filters: InventoryFilters,
        low_stock_threshold: int,
    ):
        rows = cls._filtered_inventory_scope_statement(
            filters,
            low_stock_threshold,
        ).subquery()
        return select(rows.c.inventory_units).where(
            rows.c.inventory_tracked.is_(True),
            rows.c.inventory_units.is_not(None),
        )

    @staticmethod
    def _units_sold_statement(
        start_date: date,
        end_date: date,
        eligible_product_ids=None,
    ):
        statement = (
            select(func.coalesce(func.sum(OrderLineItem.quantity), 0))
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
            .where(
                OrderLineItem.quantity > 0,
                Order.processed_at >= start_date,
                Order.processed_at < end_date + timedelta(days=1),
            )
        )
        if eligible_product_ids is not None:
            statement = statement.where(
                OrderLineItem.product_id.in_(eligible_product_ids)
            )
        return statement

    @classmethod
    def _eligible_product_ids_statement(
        cls,
        filters: InventoryFilters,
        low_stock_threshold: int,
    ):
        rows = cls._filtered_inventory_scope_statement(
            filters,
            low_stock_threshold,
        ).subquery()
        return select(rows.c.product_id).where(
            rows.c.product_id.is_not(None),
            rows.c.inventory_tracked.is_(True),
            rows.c.inventory_units.is_not(None),
        ).distinct()

    @classmethod
    def _filtered_inventory_scope_statement(
        cls,
        filters: InventoryFilters,
        low_stock_threshold: int,
    ):
        available_quantity = cls._available_quantity_expression().label(
            "inventory_units"
        )
        statement = (
            select(
                ProductVariant.product_id,
                ProductVariant.inventory_tracked,
                available_quantity,
            )
            .select_from(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id, isouter=True)
            .join(
                InventoryLevel,
                InventoryLevel.inventory_item_id
                == ProductVariant.inventory_item_id,
                isouter=True,
            )
            .join(Location, Location.id == InventoryLevel.location_id, isouter=True)
        )
        return cls._apply_inventory_filters(
            statement,
            filters,
            available_quantity,
            low_stock_threshold,
        )

    @staticmethod
    def _available_quantity_expression():
        return cast(
            func.jsonb_path_query_first(
                InventoryLevel.quantities,
                cast(
                    literal('$[*] ? (@.name == "available").quantity'),
                    JSONPATH,
                ),
            ),
            Integer,
        )

    @classmethod
    def _apply_inventory_filters(
        cls,
        statement,
        filters: InventoryFilters,
        available_quantity,
        low_stock_threshold: int,
    ):
        if filters.location_ids:
            statement = statement.where(
                InventoryLevel.location_id.in_(filters.location_ids)
            )
        if filters.vendors:
            statement = statement.where(
                func.btrim(Product.vendor).in_(filters.vendors)
            )
        if filters.inventory_tracked is True:
            statement = statement.where(ProductVariant.inventory_tracked.is_(True))
        elif filters.inventory_tracked is False:
            statement = statement.where(
                ProductVariant.inventory_tracked.is_not(True)
            )
        if filters.inventory_statuses:
            statement = statement.where(
                cls._inventory_status_expression(
                    available_quantity,
                    low_stock_threshold,
                ).in_(filters.inventory_statuses)
            )
        return statement

    @staticmethod
    def _inventory_status_expression(available_quantity, low_stock_threshold: int):
        return case(
            (
                ProductVariant.inventory_tracked.is_not(True),
                literal("untracked"),
            ),
            (available_quantity.is_(None), literal("unknown")),
            (available_quantity < 0, literal("negative")),
            (available_quantity == 0, literal("out_of_stock")),
            (
                available_quantity <= low_stock_threshold,
                literal("low_stock"),
            ),
            else_=literal("healthy"),
        )


def _has_inventory_filters(filters: InventoryFilters) -> bool:
    return bool(
        filters.location_ids
        or filters.vendors
        or filters.inventory_tracked is not None
        or filters.inventory_statuses
    )
