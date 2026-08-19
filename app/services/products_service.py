import re
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from app.repositories.products_repository import (
    ProductFilterOptionsData,
    ProductFilters,
    ProductDimensionRevenueRow,
    ProductPerformanceDateBounds,
    ProductPerformanceRow,
    ProductRevenueRow,
    ProductUnitsSoldRow,
    ProductsRepository,
    TopSellingProductRow,
)
from app.schemas.products import (
    ProductKpiResponse,
    ProductDimensionRevenue,
    ProductPerformanceItem,
    ProductPerformanceResponse,
    ProductRevenue,
    ProductSalesPerformanceResponse,
    ProductUnitsSold,
    TopSellingProduct,
)


ALLOWED_PRODUCT_STATUSES = frozenset({"active", "archived"})
PRODUCT_PERFORMANCE_SORTS = frozenset(
    {
        "product",
        "units_sold",
        "revenue",
        "orders",
        "inventory",
        "sales_velocity",
        "performance",
    }
)


def build_product_filters(
    start_date: date | None = None,
    end_date: date | None = None,
    product_types: list[str] | None = None,
    vendors: list[str] | None = None,
    statuses: list[str] | None = None,
) -> ProductFilters:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    normalized_statuses = tuple(
        dict.fromkeys(value.strip().lower() for value in statuses or [] if value.strip())
    )
    unsupported = sorted(set(normalized_statuses) - ALLOWED_PRODUCT_STATUSES)
    if unsupported:
        raise ValueError(f"Unsupported product status: {', '.join(unsupported)}")
    return ProductFilters(
        start_date=start_date,
        end_date=end_date,
        product_types=_clean_values(product_types),
        vendors=_clean_values(vendors),
        statuses=normalized_statuses,
    )


def _clean_values(values: list[str] | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values or [] if value.strip()))


class ProductsService:
    """Business rules for the Product Performance KPI response."""

    def __init__(self, repository: ProductsRepository) -> None:
        self.repository = repository

    def get_kpis(self, filters: ProductFilters) -> ProductKpiResponse:
        inputs = self.repository.get_kpi_inputs(filters)
        return ProductKpiResponse(
            total_products=inputs.catalog.total_products,
            total_variants=inputs.catalog.total_variants,
            top_selling_product=self._top_product(inputs.top_product),
            products_with_no_sales=max(
                inputs.catalog.total_products - inputs.sales.products_sold, 0
            ),
            filter_options=self._filter_options(inputs.filter_options),
        )

    def get_sales_performance(
        self, filters: ProductFilters
    ) -> ProductSalesPerformanceResponse:
        rows = self.repository.get_sales_performance(filters)
        return ProductSalesPerformanceResponse(
            top_selling=[self._units_sold_product(row) for row in rows.top_selling],
            low_selling=[self._units_sold_product(row) for row in rows.low_selling],
            sales_by_vendor=[
                self._dimension_revenue(row) for row in rows.sales_by_vendor
            ],
            sales_by_product_type=[
                self._dimension_revenue(row) for row in rows.sales_by_product_type
            ],
            product_revenue_contribution=[
                self._product_revenue(row)
                for row in rows.product_revenue_contribution
            ],
            currency=rows.currency_code,
        )

    def get_performance_table(
        self,
        filters: ProductFilters,
        page: int = 1,
        page_size: int = 10,
        search: str = "",
        sort_by: str = "units_sold",
        sort_direction: str = "desc",
    ) -> ProductPerformanceResponse:
        if sort_by not in PRODUCT_PERFORMANCE_SORTS:
            raise ValueError(f"Unsupported product performance sort: {sort_by}")
        if sort_direction not in {"asc", "desc"}:
            raise ValueError("sort_direction must be asc or desc")
        bounds = self.repository.get_performance_date_bounds(filters)
        reporting_days = self._reporting_days(filters, bounds)
        result = self.repository.get_performance_table(
            filters,
            page,
            page_size,
            search.strip(),
            sort_by,
            sort_direction,
            reporting_days,
        )
        return ProductPerformanceResponse(
            items=[
                self._performance_item(row, reporting_days) for row in result.rows
            ],
            pagination={
                "page": page,
                "page_size": page_size,
                "total_items": result.total_items,
                "total_pages": ceil(result.total_items / page_size)
                if result.total_items
                else 0,
            },
            reporting_days=reporting_days,
            currency=result.currency_code,
        )

    @classmethod
    def _performance_item(
        cls,
        row: ProductPerformanceRow,
        reporting_days: int,
    ) -> ProductPerformanceItem:
        velocity = (Decimal(row.units_sold) / Decimal(reporting_days)).quantize(
            Decimal("0.1"),
            rounding=ROUND_HALF_UP,
        )
        return ProductPerformanceItem(
            product_id=row.product_id,
            product_name=(row.product_name or "").strip()
            or cls._fallback_product_name(row.product_id),
            image_url=(row.image_url or "").strip() or None,
            status=(row.status or "unknown").strip().lower() or "unknown",
            units_sold=row.units_sold,
            revenue=row.revenue,
            orders=row.orders,
            inventory=row.inventory,
            sales_velocity=float(velocity),
            performance=cls._performance_classification(row),
        )

    @staticmethod
    def _performance_classification(row: ProductPerformanceRow) -> str:
        if row.units_sold == 0:
            return "no_sales"
        percentile = Decimal(row.sales_percentile or 0)
        if percentile <= Decimal("0.2"):
            return "top_seller"
        if percentile >= Decimal("0.8"):
            return "slow_moving"
        return "healthy"

    @staticmethod
    def _reporting_days(
        filters: ProductFilters,
        bounds: ProductPerformanceDateBounds,
        today: date | None = None,
    ) -> int:
        current_date = today or datetime.now(timezone.utc).date()
        first = bounds.first_processed_at.date() if bounds.first_processed_at else None
        last = bounds.last_processed_at.date() if bounds.last_processed_at else None
        start = filters.start_date or first or filters.end_date or current_date
        end = filters.end_date or last or current_date
        if end < start:
            end = start
        return max((end - start).days + 1, 1)

    @staticmethod
    def _dimension_revenue(
        row: ProductDimensionRevenueRow,
    ) -> ProductDimensionRevenue:
        return ProductDimensionRevenue(label=row.label, revenue=row.revenue)

    @classmethod
    def _product_revenue(cls, row: ProductRevenueRow) -> ProductRevenue:
        return ProductRevenue(
            product_id=row.product_id,
            product_name=(row.product_name or "").strip()
            or cls._fallback_product_name(row.product_id),
            revenue=row.revenue,
        )

    @classmethod
    def _units_sold_product(cls, row: ProductUnitsSoldRow) -> ProductUnitsSold:
        return ProductUnitsSold(
            product_id=row.product_id,
            product_name=(row.product_name or "").strip()
            or cls._fallback_product_name(row.product_id),
            units_sold=row.units_sold,
        )

    @staticmethod
    def _filter_options(options: ProductFilterOptionsData):
        return {
            "product_types": list(options.product_types),
            "vendors": list(options.vendors),
            "statuses": [
                {"value": "active", "label": "Active"},
                {"value": "archived", "label": "Archived"},
            ],
        }

    @classmethod
    def _top_product(
        cls, row: TopSellingProductRow | None
    ) -> TopSellingProduct | None:
        if row is None:
            return None
        return TopSellingProduct(
            product_id=row.product_id,
            product_name=(row.product_name or "").strip()
            or cls._fallback_product_name(row.product_id),
            image_url=(row.image_url or "").strip() or None,
            units_sold=row.units_sold or 0,
        )

    @staticmethod
    def _fallback_product_name(product_id: str) -> str:
        match = re.search(r"/(\d+)$", product_id)
        return f"Product {match.group(1)}" if match else "Unnamed product"
