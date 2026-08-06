from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import Integer, case, cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONPATH
from sqlalchemy.orm import Session

from app.db.models import (
    Inventory,
    Location,
    Order,
    OrderLineItem,
    Product,
    ProductVariant,
)


InventoryStatus = Literal["in_stock", "low_stock", "out_of_stock"]


@dataclass(frozen=True)
class OverviewFilters:
    start_date: date | None = None
    end_date: date | None = None
    financial_statuses: tuple[str, ...] = ()
    fulfillment_statuses: tuple[str, ...] = ()
    inventory_status: InventoryStatus | None = None
    location_ids: tuple[str, ...] = ()

    @property
    def has_order_filters(self) -> bool:
        return bool(
            self.start_date
            or self.end_date
            or self.financial_statuses
            or self.fulfillment_statuses
        )

    @property
    def has_inventory_filters(self) -> bool:
        return bool(self.inventory_status or self.location_ids)


@dataclass(frozen=True)
class OverviewSalesMetrics:
    total_revenue: Decimal | None
    total_orders: int
    currency_code: str | None


@dataclass(frozen=True)
class DashboardSummaryMetrics:
    total_products: int
    total_variants: int
    low_stock_products: int
    out_of_stock_products: int
    total_orders: int
    total_revenue: Decimal
    units_sold: int


@dataclass(frozen=True)
class InventoryHealthMetrics:
    products_with_inventory: int
    low_stock_count: int
    out_of_stock_count: int


@dataclass(frozen=True)
class InventoryAffectedProduct:
    product_id: str
    product_title: str | None
    is_out_of_stock: bool
    low_stock_quantity: int | None


@dataclass(frozen=True)
class TopProductMetrics:
    product_id: str
    product_title: str | None
    units_sold: int
    product_revenue: Decimal
    currency_code: str | None


@dataclass(frozen=True)
class LocationOption:
    id: str
    name: str


@dataclass(frozen=True)
class OverviewFilterOptions:
    financial_statuses: tuple[str, ...]
    fulfillment_statuses: tuple[str, ...]
    locations: tuple[LocationOption, ...]


class DashboardRepository:
    """PostgreSQL queries used by the filtered Store Overview."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_filter_options(self) -> OverviewFilterOptions:
        financial_statuses = tuple(
            self.db.scalars(
                select(Order.financial_status)
                .where(Order.financial_status.is_not(None))
                .distinct()
                .order_by(Order.financial_status)
            ).all()
        )
        fulfillment_statuses = tuple(
            self.db.scalars(
                select(Order.fulfillment_status)
                .where(Order.fulfillment_status.is_not(None))
                .distinct()
                .order_by(Order.fulfillment_status)
            ).all()
        )
        location_rows = self.db.execute(
            select(Location.id, Location.name)
            .join(Inventory, Inventory.location_id == Location.id)
            .where(Location.name.is_not(None))
            .distinct()
            .order_by(Location.name, Location.id)
        ).all()
        return OverviewFilterOptions(
            financial_statuses=financial_statuses,
            fulfillment_statuses=fulfillment_statuses,
            locations=tuple(
                LocationOption(id=row.id, name=row.name) for row in location_rows
            ),
        )

    def get_dashboard_summary(
        self,
        filters: OverviewFilters,
        low_stock_threshold: int,
    ) -> DashboardSummaryMetrics:
        inventory_rows = self._filtered_inventory_rows(
            filters, low_stock_threshold
        ).subquery()

        if filters.has_inventory_filters:
            total_products = self.db.scalar(
                select(func.count(func.distinct(inventory_rows.c.product_id)))
            ) or 0
            total_variants = self.db.scalar(
                select(func.count(func.distinct(inventory_rows.c.variant_id)))
            ) or 0
        else:
            total_products = self.db.scalar(
                select(func.count()).select_from(Product)
            ) or 0
            total_variants = self.db.scalar(
                select(func.count()).select_from(ProductVariant)
            ) or 0

        inventory = self._inventory_health_from_rows(
            inventory_rows, low_stock_threshold
        )
        sales = self.get_sales_metrics(filters)
        units_statement = (
            select(func.coalesce(func.sum(OrderLineItem.quantity), 0))
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
        )
        units_statement = self._apply_order_filters(units_statement, filters)
        units_sold = self.db.scalar(units_statement) or 0

        return DashboardSummaryMetrics(
            total_products=total_products,
            total_variants=total_variants,
            low_stock_products=inventory.low_stock_count,
            out_of_stock_products=inventory.out_of_stock_count,
            total_orders=sales.total_orders,
            total_revenue=sales.total_revenue or Decimal("0"),
            units_sold=units_sold,
        )

    def get_sales_metrics(
        self, filters: OverviewFilters = OverviewFilters()
    ) -> OverviewSalesMetrics:
        revenue_statement = (
            select(func.sum(OrderLineItem.unit_price * OrderLineItem.quantity))
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
        )
        revenue_statement = self._apply_order_filters(revenue_statement, filters)

        order_count_statement = select(func.count()).select_from(Order)
        order_count_statement = self._apply_order_filters(
            order_count_statement, filters
        )

        currency_statement = select(
            func.coalesce(
                func.max(OrderLineItem.currency_code),
                func.max(Order.currency_code),
            )
        ).select_from(Order).join(
            OrderLineItem, OrderLineItem.order_id == Order.id, isouter=True
        )
        currency_statement = self._apply_order_filters(currency_statement, filters)

        return OverviewSalesMetrics(
            total_revenue=self.db.scalar(revenue_statement),
            total_orders=self.db.scalar(order_count_statement) or 0,
            currency_code=self.db.scalar(currency_statement),
        )

    def get_inventory_health(
        self,
        low_stock_threshold: int,
        filters: OverviewFilters = OverviewFilters(),
    ) -> InventoryHealthMetrics:
        rows = self._filtered_inventory_rows(filters, low_stock_threshold).subquery()
        return self._inventory_health_from_rows(rows, low_stock_threshold)

    def get_affected_inventory_products(
        self,
        low_stock_threshold: int,
        filters: OverviewFilters = OverviewFilters(),
    ) -> list[InventoryAffectedProduct]:
        rows = self._filtered_inventory_rows(filters, low_stock_threshold).subquery()
        out_of_stock = func.max(
            case((rows.c.inventory_quantity == 0, 1), else_=0)
        ).label("out_of_stock")
        low_stock_quantity = func.min(
            case(
                (
                    rows.c.inventory_quantity.between(1, low_stock_threshold),
                    rows.c.inventory_quantity,
                ),
                else_=None,
            )
        ).label("low_stock_quantity")
        statement = (
            select(
                rows.c.product_id,
                Product.title.label("product_title"),
                out_of_stock,
                low_stock_quantity,
            )
            .join(Product, Product.id == rows.c.product_id, isouter=True)
            .where(rows.c.product_id.is_not(None))
            .group_by(rows.c.product_id, Product.title)
            .having(or_(out_of_stock > 0, low_stock_quantity.is_not(None)))
            .order_by(rows.c.product_id.asc())
        )
        return [
            InventoryAffectedProduct(
                product_id=row.product_id,
                product_title=row.product_title,
                is_out_of_stock=bool(row.out_of_stock),
                low_stock_quantity=row.low_stock_quantity,
            )
            for row in self.db.execute(statement).all()
        ]

    def get_top_selling_product(
        self, filters: OverviewFilters = OverviewFilters()
    ) -> TopProductMetrics | None:
        units_sold = func.sum(OrderLineItem.quantity).label("units_sold")
        product_revenue = func.sum(
            func.coalesce(OrderLineItem.unit_price, 0) * OrderLineItem.quantity
        ).label("product_revenue")
        statement = (
            select(
                OrderLineItem.product_id,
                func.max(OrderLineItem.title).label("product_title"),
                units_sold,
                product_revenue,
                func.max(OrderLineItem.currency_code).label("currency_code"),
            )
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
            .where(
                OrderLineItem.product_id.is_not(None),
                OrderLineItem.quantity > 0,
            )
            .group_by(OrderLineItem.product_id)
            .order_by(
                units_sold.desc(),
                product_revenue.desc(),
                OrderLineItem.product_id.asc(),
            )
            .limit(1)
        )
        statement = self._apply_order_filters(statement, filters)
        row = self.db.execute(statement).first()
        if row is None:
            return None

        return TopProductMetrics(
            product_id=row.product_id,
            product_title=row.product_title,
            units_sold=row.units_sold,
            product_revenue=row.product_revenue,
            currency_code=row.currency_code,
        )

    def _apply_order_filters(self, statement, filters: OverviewFilters):
        if filters.start_date:
            statement = statement.where(Order.processed_at >= filters.start_date)
        if filters.end_date:
            statement = statement.where(
                Order.processed_at < filters.end_date + timedelta(days=1)
            )
        if filters.financial_statuses:
            statement = statement.where(
                Order.financial_status.in_(filters.financial_statuses)
            )
        if filters.fulfillment_statuses:
            statement = statement.where(
                Order.fulfillment_status.in_(filters.fulfillment_statuses)
            )
        return statement

    def _filtered_inventory_rows(
        self,
        filters: OverviewFilters,
        low_stock_threshold: int,
    ):
        if filters.location_ids:
            available_quantity = cast(
                func.jsonb_path_query_first(
                    Inventory.quantities,
                    cast(
                        literal('$[*] ? (@.name == "available").quantity'),
                        JSONPATH,
                    ),
                ),
                Integer,
            )
            location_inventory = (
                select(
                    Inventory.inventory_item_id,
                    func.sum(func.coalesce(available_quantity, 0)).label(
                        "inventory_quantity"
                    ),
                )
                .where(Inventory.location_id.in_(filters.location_ids))
                .group_by(Inventory.inventory_item_id)
                .subquery()
            )
            statement = select(
                ProductVariant.id.label("variant_id"),
                ProductVariant.product_id,
                location_inventory.c.inventory_quantity,
            ).join(
                location_inventory,
                location_inventory.c.inventory_item_id
                == ProductVariant.inventory_item_id,
            )
        else:
            statement = select(
                ProductVariant.id.label("variant_id"),
                ProductVariant.product_id,
                ProductVariant.inventory_quantity,
            )

        if filters.inventory_status == "out_of_stock":
            statement = statement.where(
                statement.selected_columns.inventory_quantity == 0
            )
        elif filters.inventory_status == "low_stock":
            statement = statement.where(
                statement.selected_columns.inventory_quantity.between(
                    1, low_stock_threshold
                )
            )
        elif filters.inventory_status == "in_stock":
            statement = statement.where(
                statement.selected_columns.inventory_quantity > low_stock_threshold
            )
        return statement

    def _inventory_health_from_rows(
        self,
        rows,
        low_stock_threshold: int,
    ) -> InventoryHealthMetrics:
        row = self.db.execute(
            select(
                func.count(
                    func.distinct(
                        case(
                            (
                                rows.c.inventory_quantity.is_not(None),
                                rows.c.product_id,
                            )
                        )
                    )
                ).label("products_with_inventory"),
                func.count(
                    func.distinct(
                        case(
                            (
                                rows.c.inventory_quantity.between(
                                    1, low_stock_threshold
                                ),
                                rows.c.product_id,
                            )
                        )
                    )
                ).label("low_stock_count"),
                func.count(
                    func.distinct(
                        case(
                            (rows.c.inventory_quantity == 0, rows.c.product_id)
                        )
                    )
                ).label("out_of_stock_count"),
            )
        ).one()
        return InventoryHealthMetrics(
            products_with_inventory=row.products_with_inventory or 0,
            low_stock_count=row.low_stock_count or 0,
            out_of_stock_count=row.out_of_stock_count or 0,
        )
