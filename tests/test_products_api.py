from datetime import date, datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
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
    TopSellingProductRow,
)
from app.routers.products import (
    get_product_filters,
    get_product_kpis,
    get_product_performance,
    router,
)
from app.routers.products import get_product_sales_performance
from app.schemas.products import (
    ProductKpiResponse,
    ProductPerformanceResponse,
    ProductSalesPerformanceResponse,
)


class ProductsApiTests(unittest.TestCase):
    def test_route_is_registered_once_with_response_model(self):
        route = next(route for route in router.routes if route.path == "/api/products/kpis")

        self.assertEqual(len(router.routes), 3)
        self.assertEqual(route.response_model, ProductKpiResponse)
        self.assertIn("GET", route.methods)
        self.assertIn("/api/products/kpis", app.openapi()["paths"])
        sales_route = next(
            route
            for route in router.routes
            if route.path == "/api/products/sales-performance"
        )
        self.assertEqual(sales_route.response_model, ProductSalesPerformanceResponse)
        self.assertIn("/api/products/sales-performance", app.openapi()["paths"])
        performance_route = next(
            route for route in router.routes if route.path == "/api/products/performance"
        )
        self.assertEqual(performance_route.response_model, ProductPerformanceResponse)
        self.assertIn("/api/products/performance", app.openapi()["paths"])

    @patch("app.routers.products.ProductsRepository.get_kpi_inputs")
    def test_endpoint_returns_clean_response(self, get_inputs):
        get_inputs.return_value = ProductKpiInputs(
            catalog=ProductCatalogCounts(3, 7),
            sales=ProductSalesSummary(1),
            top_product=TopSellingProductRow(
                "product-1",
                "Shirt",
                "https://cdn.shopify.com/shirt.jpg",
                4,
                Decimal("80"),
            ),
            filter_options=ProductFilterOptionsData(("Shirts",), ("Acme",)),
        )

        http_response = Response()
        response = get_product_kpis(
            response=http_response, filters=ProductFilters(), db=object()
        )

        self.assertEqual(http_response.headers["cache-control"], "no-store")

        self.assertEqual(
            response.model_dump(),
            {
                "total_products": 3,
                "total_variants": 7,
                "top_selling_product": {
                    "product_id": "product-1",
                    "product_name": "Shirt",
                    "image_url": "https://cdn.shopify.com/shirt.jpg",
                    "units_sold": 4,
                },
                "products_with_no_sales": 2,
                "filter_options": {
                    "product_types": ["Shirts"],
                    "vendors": ["Acme"],
                    "statuses": [
                        {"value": "active", "label": "Active"},
                        {"value": "archived", "label": "Archived"},
                    ],
                },
            },
        )

    @patch("app.routers.products.ProductsRepository.get_kpi_inputs")
    def test_endpoint_sanitizes_database_errors(self, get_inputs):
        get_inputs.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_product_kpis(
                response=Response(), filters=ProductFilters(), db=object()
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.detail, "Unable to retrieve product KPI data.")
        self.assertNotIn("credentials", context.exception.detail)

    def test_filter_dependency_accepts_repeated_values_and_rejects_invalid_input(self):
        filters = get_product_filters(
            date(2026, 8, 1),
            date(2026, 8, 19),
            ["Snowboard"],
            ["Snowdevil"],
            ["active"],
        )
        self.assertEqual(filters.product_types, ("Snowboard",))
        self.assertEqual(filters.vendors, ("Snowdevil",))
        self.assertEqual(filters.statuses, ("active",))

        with self.assertRaises(HTTPException) as context:
            get_product_filters(None, None, [], [], ["draft"])
        self.assertEqual(context.exception.status_code, 422)

    @patch("app.routers.products.ProductsRepository.get_sales_performance")
    def test_sales_performance_endpoint_returns_both_rankings(self, get_rankings):
        from app.repositories.products_repository import ProductUnitsSoldRow

        get_rankings.return_value = ProductSalesPerformanceRows(
            top_selling=[ProductUnitsSoldRow("product-1", "Top", 10)],
            low_selling=[ProductUnitsSoldRow("product-2", "Low", 1)],
            sales_by_vendor=[ProductDimensionRevenueRow("Acme", Decimal("100"))],
            sales_by_product_type=[
                ProductDimensionRevenueRow("Shirts", Decimal("100"))
            ],
            product_revenue_contribution=[
                ProductRevenueRow("product-1", "Top", Decimal("100"))
            ],
            currency_code="USD",
        )
        http_response = Response()

        response = get_product_sales_performance(
            response=http_response,
            filters=ProductFilters(),
            db=object(),
        )

        self.assertEqual(http_response.headers["cache-control"], "no-store")
        self.assertEqual(response.top_selling[0].product_name, "Top")
        self.assertEqual(response.low_selling[0].units_sold, 1)
        self.assertEqual(response.sales_by_vendor[0].label, "Acme")
        self.assertEqual(response.sales_by_product_type[0].label, "Shirts")
        self.assertEqual(response.product_revenue_contribution[0].revenue, 100)
        self.assertEqual(response.currency, "USD")

    @patch("app.routers.products.ProductsRepository.get_sales_performance")
    def test_sales_performance_endpoint_sanitizes_database_errors(self, get_rankings):
        get_rankings.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_product_sales_performance(
                response=Response(), filters=ProductFilters(), db=object()
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve product sales performance data.",
        )
        self.assertNotIn("credentials", context.exception.detail)

    @patch("app.routers.products.ProductsRepository.get_performance_table")
    @patch("app.routers.products.ProductsRepository.get_performance_date_bounds")
    def test_performance_endpoint_returns_paginated_table(
        self, get_bounds, get_table
    ):
        get_bounds.return_value = ProductPerformanceDateBounds(
            datetime(2026, 8, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        get_table.return_value = ProductPerformanceRows(
            rows=[
                ProductPerformanceRow(
                    "product-1", "Product", None, "active", 10,
                    Decimal("100"), 3, 8, Decimal("0"),
                )
            ],
            total_items=1,
            currency_code="USD",
        )
        http_response = Response()

        result = get_product_performance(
            response=http_response,
            page=1,
            page_size=10,
            search="",
            sort_by="units_sold",
            sort_direction="desc",
            filters=ProductFilters(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 10),
            ),
            db=object(),
        )

        self.assertEqual(http_response.headers["cache-control"], "no-store")
        self.assertEqual(result.items[0].performance, "top_seller")
        self.assertEqual(result.items[0].sales_velocity, 1)
        self.assertEqual(result.pagination.page_size, 10)

    @patch("app.routers.products.ProductsRepository.get_performance_date_bounds")
    def test_performance_endpoint_sanitizes_database_errors(self, get_bounds):
        get_bounds.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_product_performance(
                response=Response(),
                page=1,
                page_size=10,
                search="",
                sort_by="units_sold",
                sort_direction="desc",
                filters=ProductFilters(),
                db=object(),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve product performance data.",
        )
        self.assertNotIn("credentials", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
