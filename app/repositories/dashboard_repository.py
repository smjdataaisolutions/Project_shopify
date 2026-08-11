from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import String, case, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Order,
    OrderLineItem,
    Product,
    ProductVariant,
)


@dataclass(frozen=True)
class OverviewFilters:
    start_date: date | None = None
    end_date: date | None = None
    financial_statuses: tuple[str, ...] = ()
    fulfillment_statuses: tuple[str, ...] = ()
    sales_channels: tuple[str, ...] = ()

    @property
    def has_order_filters(self) -> bool:
        return bool(
            self.start_date
            or self.end_date
            or self.financial_statuses
            or self.fulfillment_statuses
            or self.sales_channels
        )

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
class InventoryActionExportRow:
    product_id: str
    product_name: str | None
    variant_title: str | None
    sku: str | None
    inventory_quantity: int | None
    location_name: str | None
    units_sold: int


@dataclass(frozen=True)
class SalesActionExportRow:
    order_id: str
    product_name: str | None
    units: int
    gross_sales: Decimal
    discount_amount: Decimal
    net_sales: Decimal


@dataclass(frozen=True)
class TopProductMetrics:
    product_id: str
    product_title: str | None
    units_sold: int
    product_revenue: Decimal
    currency_code: str | None


@dataclass(frozen=True)
class OverviewFilterOptions:
    financial_statuses: tuple[str, ...]
    fulfillment_statuses: tuple[str, ...]
    sales_channels: tuple[str, ...]


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
        sales_channels = tuple(
            self.db.scalars(
                select(Order.sales_channel)
                .where(
                    Order.sales_channel.is_not(None),
                    func.btrim(Order.sales_channel) != "",
                )
                .distinct()
                .order_by(Order.sales_channel)
            ).all()
        )
        return OverviewFilterOptions(
            financial_statuses=financial_statuses,
            fulfillment_statuses=fulfillment_statuses,
            sales_channels=sales_channels,
        )

    def get_dashboard_summary(
        self,
        filters: OverviewFilters,
        low_stock_threshold: int,
    ) -> DashboardSummaryMetrics:
        inventory_rows = self._inventory_rows().subquery()
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
    ) -> InventoryHealthMetrics:
        rows = self._inventory_rows().subquery()
        return self._inventory_health_from_rows(rows, low_stock_threshold)

    def get_affected_inventory_products(
        self,
        low_stock_threshold: int,
    ) -> list[InventoryAffectedProduct]:
        rows = self._inventory_rows().subquery()
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

    def get_inventory_action_export_rows(
        self,
        action_id: str,
        low_stock_threshold: int,
        filters: OverviewFilters = OverviewFilters(),
    ) -> list[InventoryActionExportRow]:
        """Return only variants affected by one inventory action."""
        if action_id == "inventory_out_of_stock":
            inventory_condition = ProductVariant.inventory_quantity == 0
        elif action_id == "inventory_low_stock":
            inventory_condition = ProductVariant.inventory_quantity.between(
                1, low_stock_threshold
            )
        else:
            raise LookupError(f"Unknown inventory action '{action_id}'.")

        units_sold = (
            select(
                OrderLineItem.variant_id.label("variant_id"),
                func.coalesce(func.sum(OrderLineItem.quantity), 0).label("units_sold"),
            )
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
            .where(OrderLineItem.variant_id.is_not(None))
            .group_by(OrderLineItem.variant_id)
        )
        units_sold = self._apply_order_filters(units_sold, filters).subquery()
        statement = (
            select(
                ProductVariant.product_id,
                Product.title.label("product_name"),
                func.cast(None, String).label("variant_title"),
                func.cast(None, String).label("sku"),
                ProductVariant.inventory_quantity,
                func.cast(None, String).label("location_name"),
                func.coalesce(units_sold.c.units_sold, 0).label("units_sold"),
            )
            .select_from(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id, isouter=True)
            .join(
                units_sold,
                units_sold.c.variant_id == ProductVariant.id,
                isouter=True,
            )
            .where(
                ProductVariant.product_id.is_not(None),
                inventory_condition,
            )
            .order_by(ProductVariant.product_id.asc(), ProductVariant.id.asc())
        )
        return [
            InventoryActionExportRow(*row)
            for row in self.db.execute(statement).all()
        ]

    def get_sales_action_export_rows(
        self,
        filters: OverviewFilters = OverviewFilters(),
    ) -> list[SalesActionExportRow]:
        """Return line-item aggregates contributing to an overview sales rule."""
        gross_sales = func.coalesce(
            func.sum(OrderLineItem.unit_price * OrderLineItem.quantity), 0
        ).label("gross_sales")
        units = func.coalesce(func.sum(OrderLineItem.quantity), 0).label("units")
        discount_amount = func.coalesce(func.max(Order.total_discount), 0).label(
            "discount_amount"
        )
        statement = (
            select(
                Order.id.label("order_id"),
                OrderLineItem.title.label("product_name"),
                units,
                gross_sales,
                discount_amount,
                (gross_sales - discount_amount).label("net_sales"),
            )
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
            .group_by(Order.id, OrderLineItem.title)
            .order_by(Order.id.asc(), OrderLineItem.title.asc())
        )
        statement = self._apply_order_filters(statement, filters)
        return [
            SalesActionExportRow(*row) for row in self.db.execute(statement).all()
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
        if filters.sales_channels:
            statement = statement.where(Order.sales_channel.in_(filters.sales_channels))
        return statement

    def _inventory_rows(self):
        return select(
            ProductVariant.id.label("variant_id"),
            ProductVariant.product_id,
            ProductVariant.inventory_quantity,
        )

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
