from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import Date, String, case, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Order,
    OrderLineItem,
    InventoryLevel,
    Product,
    ProductVariant,
    ShopifySyncState,
)
from app.repositories.inventory_repository import InventoryFilters, InventoryRepository


@dataclass(frozen=True)
class OverviewFilters:
    start_date: date | datetime | None = None
    end_date: date | datetime | None = None
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
    last_updated_at: datetime | None = None


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
class ProductSalesMetric:
    product_id: str
    product_title: str | None
    units_sold: int
    net_product_sales: Decimal
    currency_code: str | None


@dataclass(frozen=True)
class LastSevenDaysProductMetric:
    product_id: str
    product_title: str | None
    units_sold: int
    orders: int
    net_product_sales: Decimal
    currency_code: str | None


@dataclass(frozen=True)
class ProductSalesConcentrationResult:
    top_products: list[ProductSalesMetric]
    product_count: int
    total_net_product_sales: Decimal
    currency_code: str | None


@dataclass(frozen=True)
class InventoryExposureResult:
    inventory_available: bool
    affected_product_count: int
    low_stock_product_count: int
    out_of_stock_product_count: int
    affected_net_product_sales: Decimal
    affected_units_sold: int
    highest_impact_product: ProductSalesMetric | None
    highest_impact_inventory_status: str | None
    inventory_as_of: datetime | None
    currency_code: str | None


@dataclass(frozen=True)
class OverviewFilterOptions:
    financial_statuses: tuple[str, ...]
    fulfillment_statuses: tuple[str, ...]
    sales_channels: tuple[str, ...]


@dataclass(frozen=True)
class DailyStorePerformanceRow:
    date: date
    total_sales: Decimal
    orders: int
    units_sold: int


@dataclass(frozen=True)
class DailyStorePerformanceResult:
    rows: list[DailyStorePerformanceRow]
    total_items: int
    total_sales: Decimal
    total_orders: int
    total_units_sold: int
    currency_code: str | None


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

    def get_daily_store_performance(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
        filters: OverviewFilters = OverviewFilters(),
    ) -> DailyStorePerformanceResult:
        daily = self._daily_store_performance_statement(filters).subquery()
        summary = self.db.execute(
            select(
                func.count().label("total_items"),
                func.coalesce(func.sum(daily.c.total_sales), 0).label(
                    "total_sales"
                ),
                func.coalesce(func.sum(daily.c.orders), 0).label("total_orders"),
                func.coalesce(func.sum(daily.c.units_sold), 0).label(
                    "total_units_sold"
                ),
                func.max(daily.c.currency_code).label("currency_code"),
            ).select_from(daily)
        ).one()

        statement = self._daily_store_performance_page_statement(
            daily,
            page,
            page_size,
            sort_by,
            sort_order,
        )
        return DailyStorePerformanceResult(
            rows=[
                DailyStorePerformanceRow(*row)
                for row in self.db.execute(statement).all()
            ],
            total_items=summary.total_items or 0,
            total_sales=summary.total_sales or Decimal("0"),
            total_orders=summary.total_orders or 0,
            total_units_sold=summary.total_units_sold or 0,
            currency_code=summary.currency_code,
        )

    @staticmethod
    def _daily_store_performance_page_statement(
        daily,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ):
        sort_columns = {
            "date": daily.c.date,
            "total_sales": daily.c.total_sales,
            "orders": daily.c.orders,
            "units_sold": daily.c.units_sold,
            "average_order_value": (
                daily.c.total_sales / func.nullif(daily.c.orders, 0)
            ),
        }
        sort_column = sort_columns[sort_by]
        primary_order = (
            sort_column.desc() if sort_order == "desc" else sort_column.asc()
        )
        return (
            select(
                daily.c.date,
                daily.c.total_sales,
                daily.c.orders,
                daily.c.units_sold,
            )
            .order_by(primary_order, daily.c.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

    def _daily_store_performance_statement(
        self,
        filters: OverviewFilters = OverviewFilters(),
    ):
        """Aggregate line items per order before producing daily metrics."""
        line_items = (
            select(
                OrderLineItem.order_id,
                func.coalesce(
                    func.sum(OrderLineItem.unit_price * OrderLineItem.quantity),
                    0,
                ).label("total_sales"),
                func.coalesce(func.sum(OrderLineItem.quantity), 0).label(
                    "units_sold"
                ),
                func.max(OrderLineItem.currency_code).label("currency_code"),
            )
            .where(OrderLineItem.order_id.is_not(None))
            .group_by(OrderLineItem.order_id)
            .subquery()
        )
        processed_date = func.timezone("UTC", Order.processed_at).cast(Date)
        order_rows = (
            select(
                processed_date.label("date"),
                Order.id.label("order_id"),
                func.coalesce(line_items.c.total_sales, 0).label("total_sales"),
                func.coalesce(line_items.c.units_sold, 0).label("units_sold"),
                func.coalesce(
                    line_items.c.currency_code,
                    Order.currency_code,
                ).label("currency_code"),
            )
            .select_from(Order)
            .join(line_items, line_items.c.order_id == Order.id, isouter=True)
            .where(Order.processed_at.is_not(None))
        )
        order_rows = self._apply_order_filters(order_rows, filters).subquery()
        return (
            select(
                order_rows.c.date,
                func.coalesce(func.sum(order_rows.c.total_sales), 0).label(
                    "total_sales"
                ),
                func.count(func.distinct(order_rows.c.order_id)).label("orders"),
                func.coalesce(func.sum(order_rows.c.units_sold), 0).label(
                    "units_sold"
                ),
                func.max(order_rows.c.currency_code).label("currency_code"),
            )
            .group_by(order_rows.c.date)
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
            last_updated_at=self.db.scalar(
                select(ShopifySyncState.last_successful_sync_at).where(
                    ShopifySyncState.source == "shopify"
                )
            ),
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

    def get_product_sales_concentration(
        self,
        filters: OverviewFilters = OverviewFilters(),
    ) -> ProductSalesConcentrationResult:
        """Return complete-period product net sales and the leading products."""
        product_sales = self._product_net_sales_statement(filters).subquery()
        summary = self.db.execute(
            select(
                func.count().label("product_count"),
                func.coalesce(func.sum(product_sales.c.net_product_sales), 0).label(
                    "total_net_product_sales"
                ),
                func.max(product_sales.c.currency_code).label("currency_code"),
            ).select_from(product_sales)
        ).one()
        top_rows = self.db.execute(
            select(
                product_sales.c.product_id,
                product_sales.c.product_title,
                product_sales.c.units_sold,
                product_sales.c.net_product_sales,
                product_sales.c.currency_code,
            )
            .order_by(
                product_sales.c.net_product_sales.desc(),
                product_sales.c.product_id.asc(),
            )
            .limit(3)
        ).all()
        return ProductSalesConcentrationResult(
            top_products=[ProductSalesMetric(*row) for row in top_rows],
            product_count=summary.product_count or 0,
            total_net_product_sales=(
                summary.total_net_product_sales or Decimal("0")
            ),
            currency_code=summary.currency_code,
        )

    def get_top_products_by_units(
        self,
        filters: OverviewFilters,
        limit: int = 5,
    ) -> list[LastSevenDaysProductMetric]:
        """Return product-level rolling-period metrics without variant duplication."""
        product_sales = self._product_net_sales_statement(filters).subquery()
        statement = (
            select(
                product_sales.c.product_id,
                product_sales.c.product_title,
                product_sales.c.units_sold,
                product_sales.c.orders,
                product_sales.c.net_product_sales,
                product_sales.c.currency_code,
            )
            .order_by(
                product_sales.c.units_sold.desc(),
                product_sales.c.net_product_sales.desc(),
                product_sales.c.product_id.asc(),
            )
            .limit(limit)
        )
        return [
            LastSevenDaysProductMetric(*row)
            for row in self.db.execute(statement).all()
        ]

    def get_inventory_exposure(
        self,
        low_stock_threshold: int,
        filters: OverviewFilters = OverviewFilters(),
    ) -> InventoryExposureResult:
        """Connect selected-period product sales to current Product View status."""
        product_sales = self._product_net_sales_statement(filters).subquery()
        inventory_products = InventoryRepository.product_inventory_scope_statement(
            InventoryFilters(),
            low_stock_threshold,
        ).subquery()
        inventory_status = case(
            (inventory_products.c.inventory_units == 0, "out_of_stock"),
            (
                inventory_products.c.inventory_units.between(
                    1,
                    low_stock_threshold,
                ),
                "low_stock",
            ),
            else_=None,
        ).label("inventory_status")
        affected = (
            select(
                product_sales.c.product_id,
                product_sales.c.product_title,
                product_sales.c.units_sold,
                product_sales.c.net_product_sales,
                product_sales.c.currency_code,
                inventory_status,
            )
            .select_from(product_sales)
            .join(
                inventory_products,
                inventory_products.c.product_id == product_sales.c.product_id,
            )
            .where(
                inventory_products.c.inventory_tracked.is_(True),
                inventory_products.c.inventory_units.is_not(None),
                inventory_status.is_not(None),
            )
            .subquery()
        )
        summary = self.db.execute(
            select(
                func.count().label("affected_product_count"),
                func.count()
                .filter(affected.c.inventory_status == "low_stock")
                .label("low_stock_product_count"),
                func.count()
                .filter(affected.c.inventory_status == "out_of_stock")
                .label("out_of_stock_product_count"),
                func.coalesce(func.sum(affected.c.net_product_sales), 0).label(
                    "affected_net_product_sales"
                ),
                func.coalesce(func.sum(affected.c.units_sold), 0).label(
                    "affected_units_sold"
                ),
                func.max(affected.c.currency_code).label("currency_code"),
            ).select_from(affected)
        ).one()
        top_row = self.db.execute(
            select(
                affected.c.product_id,
                affected.c.product_title,
                affected.c.units_sold,
                affected.c.net_product_sales,
                affected.c.currency_code,
                affected.c.inventory_status,
            )
            .order_by(
                affected.c.net_product_sales.desc(),
                affected.c.product_id.asc(),
            )
            .limit(1)
        ).first()
        inventory_product_count = self.db.scalar(
            select(func.count())
            .select_from(inventory_products)
            .where(
                inventory_products.c.inventory_tracked.is_(True),
                inventory_products.c.inventory_units.is_not(None),
            )
        ) or 0
        inventory_as_of = self.db.scalar(select(func.max(InventoryLevel.updated_at)))
        highest_impact = None
        highest_impact_status = None
        if top_row is not None:
            highest_impact = ProductSalesMetric(
                product_id=top_row.product_id,
                product_title=top_row.product_title,
                units_sold=top_row.units_sold,
                net_product_sales=top_row.net_product_sales,
                currency_code=top_row.currency_code,
            )
            highest_impact_status = top_row.inventory_status
        return InventoryExposureResult(
            inventory_available=inventory_product_count > 0,
            affected_product_count=summary.affected_product_count or 0,
            low_stock_product_count=summary.low_stock_product_count or 0,
            out_of_stock_product_count=summary.out_of_stock_product_count or 0,
            affected_net_product_sales=(
                summary.affected_net_product_sales or Decimal("0")
            ),
            affected_units_sold=summary.affected_units_sold or 0,
            highest_impact_product=highest_impact,
            highest_impact_inventory_status=highest_impact_status,
            inventory_as_of=inventory_as_of,
            currency_code=summary.currency_code,
        )

    def _product_net_sales_statement(
        self,
        filters: OverviewFilters = OverviewFilters(),
    ):
        """Allocate order discounts/refunds by line gross sales, then aggregate."""
        line_gross = (
            func.coalesce(OrderLineItem.unit_price, 0)
            * func.coalesce(OrderLineItem.quantity, 0)
        )
        order_gross = (
            select(
                OrderLineItem.order_id,
                func.coalesce(func.sum(line_gross), 0).label("order_gross"),
            )
            .where(
                OrderLineItem.order_id.is_not(None),
                OrderLineItem.quantity > 0,
            )
            .group_by(OrderLineItem.order_id)
            .subquery()
        )
        product_order_sales = (
            select(
                OrderLineItem.order_id,
                OrderLineItem.product_id,
                func.coalesce(
                    func.max(Product.title),
                    func.max(OrderLineItem.title),
                ).label("product_title"),
                func.coalesce(func.sum(OrderLineItem.quantity), 0).label(
                    "units_sold"
                ),
                func.coalesce(func.sum(line_gross), 0).label("product_gross"),
                order_gross.c.order_gross,
                func.coalesce(Order.total_discount, 0).label("order_discount"),
                func.coalesce(Order.total_refunded, 0).label("order_refunded"),
                func.coalesce(
                    func.max(OrderLineItem.currency_code),
                    Order.currency_code,
                ).label("currency_code"),
            )
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
            .join(order_gross, order_gross.c.order_id == OrderLineItem.order_id)
            .join(Product, Product.id == OrderLineItem.product_id, isouter=True)
            .where(
                OrderLineItem.product_id.is_not(None),
                OrderLineItem.quantity > 0,
            )
            .group_by(
                OrderLineItem.order_id,
                OrderLineItem.product_id,
                order_gross.c.order_gross,
                Order.total_discount,
                Order.total_refunded,
                Order.currency_code,
            )
        )
        product_order_sales = self._apply_order_filters(
            product_order_sales,
            filters,
        ).subquery()
        allocated_adjustment = case(
            (
                product_order_sales.c.order_gross > 0,
                (
                    product_order_sales.c.order_discount
                    + product_order_sales.c.order_refunded
                )
                * product_order_sales.c.product_gross
                / product_order_sales.c.order_gross,
            ),
            else_=0,
        )
        return (
            select(
                product_order_sales.c.product_id,
                func.max(product_order_sales.c.product_title).label(
                    "product_title"
                ),
                func.coalesce(func.sum(product_order_sales.c.units_sold), 0).label(
                    "units_sold"
                ),
                func.count(func.distinct(product_order_sales.c.order_id)).label(
                    "orders"
                ),
                func.coalesce(
                    func.sum(
                        product_order_sales.c.product_gross - allocated_adjustment
                    ),
                    0,
                ).label("net_product_sales"),
                func.max(product_order_sales.c.currency_code).label(
                    "currency_code"
                ),
            )
            .group_by(product_order_sales.c.product_id)
        )

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
