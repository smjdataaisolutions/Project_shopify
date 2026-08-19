from datetime import date, datetime, timezone
from decimal import Decimal
import unittest

from app.repositories.products_repository import (
    ProductCatalogCounts,
    ProductFilterOptionsData,
    ProductFilters,
    ProductKpiInputs,
    ProductDimensionRevenueRow,
    ProductPerformanceDateBounds,
    ProductPerformanceRow,
    ProductPerformanceRows,
    ProductRevenueRow,
    ProductSalesPerformanceRows,
    ProductSalesSummary,
    ProductUnitsSoldRow,
    TopSellingProductRow,
)
from app.services.products_service import ProductsService, build_product_filters


class StubProductsRepository:
    def __init__(self, inputs):
        self.inputs = inputs
        self.called = False

    def get_kpi_inputs(self, filters):
        self.called = True
        self.filters = filters
        return self.inputs

    def get_sales_performance(self, filters):
        self.filters = filters
        return ProductSalesPerformanceRows(
            top_selling=[
                ProductUnitsSoldRow("product-1", " Best Seller ", 12),
                ProductUnitsSoldRow("product-2", None, 5),
            ],
            low_selling=[ProductUnitsSoldRow("product-2", None, 5)],
            sales_by_vendor=[ProductDimensionRevenueRow("Acme", Decimal("75"))],
            sales_by_product_type=[
                ProductDimensionRevenueRow("Shirts", Decimal("75"))
            ],
            product_revenue_contribution=[
                ProductRevenueRow("product-1", " Best Seller ", Decimal("75"))
            ],
            currency_code="USD",
        )

    def get_performance_date_bounds(self, filters):
        self.filters = filters
        return ProductPerformanceDateBounds(
            datetime(2026, 8, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 10, tzinfo=timezone.utc),
        )

    def get_performance_table(
        self,
        filters,
        page,
        page_size,
        search,
        sort_by,
        sort_direction,
        reporting_days,
    ):
        self.performance_request = (
            filters,
            page,
            page_size,
            search,
            sort_by,
            sort_direction,
            reporting_days,
        )
        return ProductPerformanceRows(
            rows=[
                ProductPerformanceRow(
                    "product-1", " Top ", " https://cdn/top.jpg ", "ACTIVE", 20,
                    Decimal("200"), 8, 4, Decimal("0"),
                ),
                ProductPerformanceRow(
                    "product-2", "Healthy", None, "draft", 10,
                    Decimal("100"), 4, None, Decimal("0.5"),
                ),
                ProductPerformanceRow(
                    "product-3", "Slow", None, "archived", 1,
                    Decimal("10"), 1, 15, Decimal("1"),
                ),
                ProductPerformanceRow(
                    "product-4", None, None, None, 0,
                    Decimal("0"), 0, 0, None,
                ),
            ],
            total_items=4,
            currency_code="USD",
        )


class ProductsServiceTests(unittest.TestCase):
    def test_kpis_apply_no_sales_and_top_product_rules(self):
        repository = StubProductsRepository(
            ProductKpiInputs(
                catalog=ProductCatalogCounts(5, 12),
                sales=ProductSalesSummary(2),
                top_product=TopSellingProductRow(
                    "gid://shopify/Product/101",
                    " Classic Shirt ",
                    " https://cdn.shopify.com/shirt.jpg ",
                    6,
                    Decimal("70"),
                ),
                filter_options=ProductFilterOptionsData(
                    ("Snowboard",), ("Snowdevil",)
                ),
            )
        )
        filters = ProductFilters(statuses=("active",))
        response = ProductsService(repository).get_kpis(filters)

        self.assertTrue(repository.called)
        self.assertEqual(repository.filters, filters)
        self.assertEqual(response.total_products, 5)
        self.assertEqual(response.total_variants, 12)
        self.assertEqual(response.products_with_no_sales, 3)
        self.assertEqual(response.top_selling_product.product_name, "Classic Shirt")
        self.assertEqual(
            response.top_selling_product.image_url,
            "https://cdn.shopify.com/shirt.jpg",
        )
        self.assertEqual(response.top_selling_product.units_sold, 6)
        self.assertEqual(response.filter_options.product_types, ["Snowboard"])
        self.assertEqual(response.filter_options.vendors, ["Snowdevil"])
        self.assertEqual(
            [option.value for option in response.filter_options.statuses],
            ["active", "archived"],
        )

    def test_empty_sales_return_safe_values_without_fabricating_top_product(self):
        repository = StubProductsRepository(
            ProductKpiInputs(
                catalog=ProductCatalogCounts(4, 10),
                sales=ProductSalesSummary(0),
                top_product=None,
                filter_options=ProductFilterOptionsData((), ()),
            )
        )

        response = ProductsService(repository).get_kpis(ProductFilters())

        self.assertEqual(response.products_with_no_sales, 4)
        self.assertIsNone(response.top_selling_product)

    def test_missing_top_product_name_uses_fallback(self):
        repository = StubProductsRepository(
            ProductKpiInputs(
                catalog=ProductCatalogCounts(1, 1),
                sales=ProductSalesSummary(1),
                top_product=TopSellingProductRow(
                    "product-1", None, None, 1, Decimal("10")
                ),
                filter_options=ProductFilterOptionsData((), ()),
            )
        )

        response = ProductsService(repository).get_kpis(ProductFilters())

        self.assertEqual(response.top_selling_product.product_name, "Unnamed product")
        self.assertIsNone(response.top_selling_product.image_url)

    def test_build_filters_validates_dates_statuses_and_cleans_values(self):
        filters = build_product_filters(
            date(2026, 8, 1),
            date(2026, 8, 19),
            [" Snowboard ", "Snowboard"],
            [" Snowdevil "],
            ["ACTIVE", "archived"],
        )
        self.assertEqual(filters.product_types, ("Snowboard",))
        self.assertEqual(filters.vendors, ("Snowdevil",))
        self.assertEqual(filters.statuses, ("active", "archived"))

        with self.assertRaisesRegex(ValueError, "start_date"):
            build_product_filters(date(2026, 8, 20), date(2026, 8, 19))
        with self.assertRaisesRegex(ValueError, "Unsupported product status"):
            build_product_filters(statuses=["draft"])

    def test_sales_performance_maps_ranked_rows_and_fallback_names(self):
        repository = StubProductsRepository(None)
        filters = ProductFilters(vendors=("Acme",))

        response = ProductsService(repository).get_sales_performance(filters)

        self.assertEqual(repository.filters, filters)
        self.assertEqual(
            [item.product_name for item in response.top_selling],
            ["Best Seller", "Unnamed product"],
        )
        self.assertEqual(response.low_selling[0].units_sold, 5)
        self.assertEqual(response.sales_by_vendor[0].label, "Acme")
        self.assertEqual(response.sales_by_product_type[0].label, "Shirts")
        self.assertEqual(
            response.product_revenue_contribution[0].product_name,
            "Best Seller",
        )
        self.assertEqual(response.currency, "USD")

    def test_performance_table_applies_velocity_classification_and_pagination(self):
        repository = StubProductsRepository(None)
        filters = ProductFilters(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 10),
        )

        response = ProductsService(repository).get_performance_table(
            filters,
            page=1,
            page_size=10,
            search=" Top ",
            sort_by="revenue",
            sort_direction="desc",
        )

        self.assertEqual(response.reporting_days, 10)
        self.assertEqual(
            [item.performance for item in response.items],
            ["top_seller", "healthy", "slow_moving", "no_sales"],
        )
        self.assertEqual([item.sales_velocity for item in response.items], [2, 1, 0.1, 0])
        self.assertEqual(response.items[0].product_name, "Top")
        self.assertEqual(response.items[0].image_url, "https://cdn/top.jpg")
        self.assertEqual(response.items[3].product_name, "Unnamed product")
        self.assertEqual(response.pagination.total_pages, 1)
        self.assertEqual(response.currency, "USD")
        self.assertEqual(repository.performance_request[3], "Top")

    def test_reporting_days_uses_inclusive_dates_and_safe_single_day(self):
        bounds = ProductPerformanceDateBounds(None, None)
        self.assertEqual(
            ProductsService._reporting_days(
                ProductFilters(
                    start_date=date(2026, 8, 1),
                    end_date=date(2026, 8, 1),
                ),
                bounds,
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
