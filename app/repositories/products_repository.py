from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderLineItem, Product, ProductVariant
from app.repositories.inventory_repository import InventoryRepository


@dataclass(frozen=True)
class ProductFilters:
    start_date: date | None = None
    end_date: date | None = None
    product_types: tuple[str, ...] = ()
    vendors: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductCatalogCounts:
    total_products: int
    total_variants: int


@dataclass(frozen=True)
class ProductSalesSummary:
    products_sold: int


@dataclass(frozen=True)
class ProductFilterOptionsData:
    product_types: tuple[str, ...]
    vendors: tuple[str, ...]


@dataclass(frozen=True)
class TopSellingProductRow:
    product_id: str
    product_name: str | None
    image_url: str | None
    units_sold: int
    product_revenue: Decimal


@dataclass(frozen=True)
class ProductUnitsSoldRow:
    product_id: str
    product_name: str | None
    units_sold: int


@dataclass(frozen=True)
class ProductRevenueRow:
    product_id: str
    product_name: str | None
    revenue: Decimal


@dataclass(frozen=True)
class ProductDimensionRevenueRow:
    label: str
    revenue: Decimal


@dataclass(frozen=True)
class ProductSalesPerformanceRows:
    top_selling: list[ProductUnitsSoldRow]
    low_selling: list[ProductUnitsSoldRow]
    sales_by_vendor: list[ProductDimensionRevenueRow]
    sales_by_product_type: list[ProductDimensionRevenueRow]
    product_revenue_contribution: list[ProductRevenueRow]
    currency_code: str | None


@dataclass(frozen=True)
class ProductPerformanceDateBounds:
    first_processed_at: datetime | None
    last_processed_at: datetime | None


@dataclass(frozen=True)
class ProductPerformanceRow:
    product_id: str
    product_name: str | None
    image_url: str | None
    status: str | None
    units_sold: int
    revenue: Decimal
    orders: int
    inventory: int | None
    sales_percentile: Decimal | None


@dataclass(frozen=True)
class ProductPerformanceRows:
    rows: list[ProductPerformanceRow]
    total_items: int
    currency_code: str | None


@dataclass(frozen=True)
class ProductKpiInputs:
    catalog: ProductCatalogCounts
    sales: ProductSalesSummary
    top_product: TopSellingProductRow | None
    filter_options: ProductFilterOptionsData


class ProductsRepository:
    """PostgreSQL aggregates for product portfolio KPIs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_kpi_inputs(self, filters: ProductFilters) -> ProductKpiInputs:
        catalog_row = self.db.execute(self._catalog_counts_statement(filters)).one()
        eligible_sales = self._eligible_sales(filters)
        product_sales = self._product_sales(eligible_sales)
        sales_row = self.db.execute(
            self._sales_summary_statement(product_sales)
        ).one()
        top_row = self.db.execute(
            self._top_product_statement(product_sales)
        ).first()
        filter_options = self._get_filter_options()

        return ProductKpiInputs(
            catalog=ProductCatalogCounts(
                total_products=catalog_row.total_products or 0,
                total_variants=catalog_row.total_variants or 0,
            ),
            sales=ProductSalesSummary(
                products_sold=sales_row.products_sold or 0,
            ),
            top_product=TopSellingProductRow(*top_row) if top_row else None,
            filter_options=filter_options,
        )

    def get_sales_performance(
        self, filters: ProductFilters
    ) -> ProductSalesPerformanceRows:
        eligible_sales = self._eligible_sales(filters)
        product_sales = self._product_sales(eligible_sales)
        top_rows = self.db.execute(
            self._ranked_product_units_statement(product_sales, descending=True)
        ).all()
        low_rows = self.db.execute(
            self._ranked_product_units_statement(product_sales, descending=False)
        ).all()
        vendor_rows = self.db.execute(
            self._dimension_revenue_statement(eligible_sales, "vendor")
        ).all()
        product_type_rows = self.db.execute(
            self._dimension_revenue_statement(eligible_sales, "product_type")
        ).all()
        product_revenue_rows = self.db.execute(
            self._product_revenue_statement(product_sales)
        ).all()
        currency_row = self.db.execute(
            self._sales_currency_statement(eligible_sales)
        ).one()
        return ProductSalesPerformanceRows(
            top_selling=[ProductUnitsSoldRow(*row) for row in top_rows],
            low_selling=[ProductUnitsSoldRow(*row) for row in low_rows],
            sales_by_vendor=[ProductDimensionRevenueRow(*row) for row in vendor_rows],
            sales_by_product_type=[
                ProductDimensionRevenueRow(*row) for row in product_type_rows
            ],
            product_revenue_contribution=[
                ProductRevenueRow(*row) for row in product_revenue_rows
            ],
            currency_code=(
                currency_row.currency_code
                if currency_row.currency_count == 1
                else None
            ),
        )

    def get_performance_date_bounds(
        self, filters: ProductFilters
    ) -> ProductPerformanceDateBounds:
        eligible_sales = self._eligible_sales(filters)
        row = self.db.execute(
            select(
                func.min(eligible_sales.c.processed_at),
                func.max(eligible_sales.c.processed_at),
            )
        ).one()
        return ProductPerformanceDateBounds(*row)

    def get_performance_table(
        self,
        filters: ProductFilters,
        page: int,
        page_size: int,
        search: str,
        sort_by: str,
        sort_direction: str,
        reporting_days: int,
    ) -> ProductPerformanceRows:
        eligible_sales = self._eligible_sales(filters)
        product_sales = self._product_sales(eligible_sales)
        performance = self._performance_base_statement(
            filters,
            product_sales,
            search,
        ).subquery()
        ranked = self._performance_ranked_statement(performance).subquery()
        total_items = self.db.scalar(
            select(func.count()).select_from(ranked)
        ) or 0
        rows = self.db.execute(
            self._performance_page_statement(
                ranked,
                page,
                page_size,
                sort_by,
                sort_direction,
                reporting_days,
            )
        ).all()
        currency_statement = self._sales_currency_statement(eligible_sales)
        if search:
            currency_statement = currency_statement.where(
                func.coalesce(eligible_sales.c.catalog_title, "").ilike(
                    self._search_pattern(search),
                    escape="\\",
                )
            )
        currency_row = self.db.execute(currency_statement).one()
        return ProductPerformanceRows(
            rows=[ProductPerformanceRow(*row) for row in rows],
            total_items=total_items,
            currency_code=(
                currency_row.currency_code
                if currency_row.currency_count == 1
                else None
            ),
        )

    def _get_filter_options(self) -> ProductFilterOptionsData:
        product_type = func.btrim(Product.product_type).label("value")
        vendor = func.btrim(Product.vendor).label("value")
        product_types = self.db.execute(
            select(product_type)
            .where(func.nullif(product_type, "").is_not(None))
            .distinct()
            .order_by(product_type)
        ).scalars().all()
        vendors = self.db.execute(
            select(vendor)
            .where(func.nullif(vendor, "").is_not(None))
            .distinct()
            .order_by(vendor)
        ).scalars().all()
        return ProductFilterOptionsData(tuple(product_types), tuple(vendors))

    @classmethod
    def _catalog_counts_statement(cls, filters: ProductFilters):
        product_scope = (
            select(Product.id)
            .where(*cls._product_predicates(filters))
            .subquery()
        )
        total_products = select(
            func.count(func.distinct(product_scope.c.id))
        ).scalar_subquery()
        total_variants = select(
            func.count(func.distinct(ProductVariant.id))
        ).where(
            ProductVariant.product_id.in_(select(product_scope.c.id))
        ).scalar_subquery()
        return select(
            total_products.label("total_products"),
            total_variants.label("total_variants"),
        )

    @classmethod
    def _eligible_sales(cls, filters: ProductFilters):
        statement = (
            select(
                OrderLineItem.product_id,
                OrderLineItem.order_id,
                Order.processed_at.label("processed_at"),
                Product.title.label("catalog_title"),
                Product.image_url.label("catalog_image_url"),
                Product.vendor.label("vendor"),
                Product.product_type.label("product_type"),
                OrderLineItem.title.label("line_title"),
                OrderLineItem.quantity,
                OrderLineItem.unit_price,
                func.coalesce(
                    OrderLineItem.currency_code,
                    Order.currency_code,
                ).label("currency_code"),
            )
            .select_from(OrderLineItem)
            .join(Order, Order.id == OrderLineItem.order_id)
            .join(Product, Product.id == OrderLineItem.product_id)
            .where(
                Order.processed_at.is_not(None),
                OrderLineItem.product_id.is_not(None),
                OrderLineItem.quantity > 0,
                *cls._product_predicates(filters),
            )
        )
        if filters.start_date:
            statement = statement.where(Order.processed_at >= filters.start_date)
        if filters.end_date:
            statement = statement.where(
                Order.processed_at < filters.end_date + timedelta(days=1)
            )
        return statement.subquery()

    @staticmethod
    def _product_predicates(filters: ProductFilters):
        predicates = []
        if filters.product_types:
            predicates.append(Product.product_type.in_(filters.product_types))
        if filters.vendors:
            predicates.append(Product.vendor.in_(filters.vendors))
        if filters.statuses:
            predicates.append(func.lower(Product.status).in_(filters.statuses))
        return predicates

    @staticmethod
    def _product_sales(eligible_sales):
        units_sold = func.coalesce(func.sum(eligible_sales.c.quantity), 0)
        product_revenue = func.coalesce(
            func.sum(
                func.coalesce(eligible_sales.c.unit_price, 0)
                * eligible_sales.c.quantity
            ),
            0,
        )
        return (
            select(
                eligible_sales.c.product_id,
                func.coalesce(
                    func.max(func.nullif(func.btrim(eligible_sales.c.catalog_title), "")),
                    func.max(func.nullif(func.btrim(eligible_sales.c.line_title), "")),
                ).label("product_name"),
                func.max(eligible_sales.c.catalog_image_url).label("image_url"),
                units_sold.label("units_sold"),
                product_revenue.label("product_revenue"),
                func.count(func.distinct(eligible_sales.c.order_id)).label("orders"),
            )
            .group_by(eligible_sales.c.product_id)
            .subquery()
        )

    @staticmethod
    def _sales_summary_statement(product_sales):
        return select(
            func.count(product_sales.c.product_id).label("products_sold"),
        )

    @staticmethod
    def _top_product_statement(product_sales):
        return (
            select(
                product_sales.c.product_id,
                product_sales.c.product_name,
                product_sales.c.image_url,
                product_sales.c.units_sold,
                product_sales.c.product_revenue,
            )
            .order_by(
                product_sales.c.units_sold.desc(),
                product_sales.c.product_revenue.desc(),
                product_sales.c.product_id.asc(),
            )
            .limit(1)
        )

    @staticmethod
    def _ranked_product_units_statement(product_sales, *, descending: bool):
        units_order = (
            product_sales.c.units_sold.desc()
            if descending
            else product_sales.c.units_sold.asc()
        )
        return (
            select(
                product_sales.c.product_id,
                product_sales.c.product_name,
                product_sales.c.units_sold,
            )
            .where(product_sales.c.units_sold > 0)
            .order_by(units_order, product_sales.c.product_id.asc())
            .limit(10)
        )

    @staticmethod
    def _dimension_revenue_statement(eligible_sales, dimension: str):
        source = getattr(eligible_sales.c, dimension)
        label = func.coalesce(
            func.nullif(func.btrim(source), ""),
            "Unknown vendor" if dimension == "vendor" else "Unknown product type",
        ).label("label")
        revenue = func.coalesce(
            func.sum(
                func.coalesce(eligible_sales.c.unit_price, 0)
                * eligible_sales.c.quantity
            ),
            0,
        ).label("revenue")
        return (
            select(label, revenue)
            .group_by(label)
            .having(revenue > 0)
            .order_by(revenue.desc(), label.asc())
            .limit(10)
        )

    @staticmethod
    def _product_revenue_statement(product_sales):
        return (
            select(
                product_sales.c.product_id,
                product_sales.c.product_name,
                product_sales.c.product_revenue.label("revenue"),
            )
            .where(product_sales.c.product_revenue > 0)
            .order_by(
                product_sales.c.product_revenue.desc(),
                product_sales.c.product_id.asc(),
            )
            .limit(10)
        )

    @staticmethod
    def _sales_currency_statement(eligible_sales):
        currency = func.nullif(func.btrim(eligible_sales.c.currency_code), "")
        return select(
            func.max(currency).label("currency_code"),
            func.count(func.distinct(currency)).label("currency_count"),
        )

    @classmethod
    def _performance_base_statement(
        cls,
        filters: ProductFilters,
        product_sales,
        search: str = "",
    ):
        inventory = InventoryRepository.product_inventory_scope_statement().subquery()
        statement = (
            select(
                Product.id.label("product_id"),
                Product.title.label("product_name"),
                Product.image_url,
                Product.status,
                func.coalesce(product_sales.c.units_sold, 0).label("units_sold"),
                func.coalesce(product_sales.c.product_revenue, 0).label("revenue"),
                func.coalesce(product_sales.c.orders, 0).label("orders"),
                inventory.c.inventory_units.label("inventory"),
            )
            .select_from(Product)
            .outerjoin(product_sales, product_sales.c.product_id == Product.id)
            .outerjoin(inventory, inventory.c.product_id == Product.id)
            .where(*cls._product_predicates(filters))
        )
        if search:
            statement = statement.where(
                func.coalesce(Product.title, "").ilike(
                    cls._search_pattern(search),
                    escape="\\",
                )
            )
        return statement

    @staticmethod
    def _search_pattern(search: str) -> str:
        escaped = (
            search.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        return f"%{escaped}%"

    @staticmethod
    def _performance_ranked_statement(performance):
        positive = (
            select(
                performance.c.product_id,
                func.percent_rank()
                .over(order_by=performance.c.units_sold.desc())
                .label("sales_percentile"),
            )
            .where(performance.c.units_sold > 0)
            .subquery()
        )
        return (
            select(
                performance.c.product_id,
                performance.c.product_name,
                performance.c.image_url,
                performance.c.status,
                performance.c.units_sold,
                performance.c.revenue,
                performance.c.orders,
                performance.c.inventory,
                positive.c.sales_percentile,
            )
            .select_from(performance)
            .outerjoin(positive, positive.c.product_id == performance.c.product_id)
        )

    @staticmethod
    def _performance_page_statement(
        ranked,
        page: int,
        page_size: int,
        sort_by: str,
        sort_direction: str,
        reporting_days: int,
    ):
        sales_velocity = ranked.c.units_sold / literal(max(reporting_days, 1))
        performance_order = case(
            (ranked.c.units_sold == 0, 3),
            (ranked.c.sales_percentile <= Decimal("0.2"), 0),
            (ranked.c.sales_percentile >= Decimal("0.8"), 2),
            else_=1,
        )
        sort_columns = {
            "product": func.lower(func.coalesce(ranked.c.product_name, "")),
            "units_sold": ranked.c.units_sold,
            "revenue": ranked.c.revenue,
            "orders": ranked.c.orders,
            "inventory": ranked.c.inventory,
            "sales_velocity": sales_velocity,
            "performance": performance_order,
        }
        column = sort_columns[sort_by]
        ordering = column.desc() if sort_direction == "desc" else column.asc()
        return (
            select(
                ranked.c.product_id,
                ranked.c.product_name,
                ranked.c.image_url,
                ranked.c.status,
                ranked.c.units_sold,
                ranked.c.revenue,
                ranked.c.orders,
                ranked.c.inventory,
                ranked.c.sales_percentile,
            )
            .order_by(ordering.nulls_last(), ranked.c.product_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
