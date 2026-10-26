from datetime import date, timedelta
from decimal import Decimal
import os
import unittest

from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy import func, select

from app.repositories.sales_repository import (
    SalesChartAggregateRow,
    SalesChartResult,
    SalesFilters,
    SalesRepository,
)
from app.routers.sales import get_sales_chart, router
from app.schemas.sales import SalesChartResponse
from app.services.sales_service import SalesService, build_sales_comparison_period
from app.db.session import SessionLocal
from app.db.models import Order


class ChartRepositoryStub:
    def __init__(self, rows):
        self.rows = rows
        self.received = None

    def get_sales_chart(self, filters, dimension, measure, product_ids=None):
        self.received = (filters, dimension, measure, product_ids)
        return SalesChartResult(self.rows, "USD")


class ComparisonRepositoryStub:
    def __init__(self, current, comparison):
        self.results = [current, comparison]
        self.calls = []

    def get_sales_chart(self, filters, dimension, measure, product_ids=None):
        self.calls.append((filters, dimension, measure, product_ids))
        return self.results[len(self.calls) - 1]


class SalesChartTests(unittest.TestCase):
    def test_default_date_revenue_response_is_chart_ready(self):
        repository = ChartRepositoryStub([
            SalesChartAggregateRow(
                "2026-08-01", date(2026, 8, 1), Decimal("125.50"), 2, 3
            )
        ])

        response = SalesService(repository).get_sales_chart(
            SalesFilters(), "processed_date", "revenue"
        )

        self.assertEqual(response.chart_type, "line")
        self.assertEqual(response.comparison, "none")
        self.assertEqual(response.comparison_data, [])
        self.assertEqual(response.data[0].model_dump(), {
            "id": "2026-08-01",
            "label": "2026-08-01",
            "value": 125.5,
        })

    def test_channel_aov_combines_sources_before_dividing(self):
        repository = ChartRepositoryStub([
            SalesChartAggregateRow("web", "web", Decimal("100"), 2, 4),
            SalesChartAggregateRow(
                "shopify_online_store",
                "shopify_online_store",
                Decimal("50"),
                1,
                2,
            ),
        ])

        response = SalesService(repository).get_sales_chart(
            SalesFilters(), "sales_channel", "average_order_value"
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].label, "Online Store")
        self.assertEqual(response.data[0].value, 50.0)

    def test_product_aov_and_unknown_dimensions_are_rejected(self):
        service = SalesService(ChartRepositoryStub([]))
        with self.assertRaisesRegex(ValueError, "not supported"):
            service.get_sales_chart(SalesFilters(), "product", "average_order_value")
        with self.assertRaisesRegex(ValueError, "Unsupported dimension"):
            service.get_sales_chart(SalesFilters(), "location", "revenue")

    def test_endpoint_returns_clean_400_for_invalid_selection(self):
        with self.assertRaises(HTTPException) as context:
            get_sales_chart(
                dimension="location",
                measure="revenue",
                filters=SalesFilters(),
                db=object(),
            )
        self.assertEqual(context.exception.status_code, 400)

    def test_route_uses_generic_chart_path_and_response_model(self):
        route = next(route for route in router.routes if route.path == "/api/sales/chart")
        self.assertEqual(route.response_model, SalesChartResponse)
        self.assertIn("GET", route.methods)

    def test_sql_aggregates_orders_without_line_item_revenue_duplication(self):
        repository = SalesRepository(object())
        statement = repository._order_chart_statement(
            SalesFilters(start_date=date(2026, 8, 1)), "processed_date"
        )
        sql = str(statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        ))
        self.assertIn("sum(orders.total_price)", sql)
        self.assertIn("GROUP BY order_line_items.order_id", sql)
        self.assertIn("count(distinct(orders.id))", sql.lower())
        self.assertIn("timezone('UTC', orders.processed_at)", sql)

    def test_product_sql_consolidates_products_and_limits_top_five(self):
        repository = SalesRepository(object())
        statement = repository._product_chart_statement(
            SalesFilters(financial_statuses=("PAID",)), "revenue"
        )
        sql = str(statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        ))
        self.assertIn("GROUP BY", sql)
        self.assertIn("order_line_items.product_id", sql)
        self.assertIn("orders.financial_status IN ('PAID')", sql)
        self.assertIn("LIMIT 5", sql)

    def test_previous_period_uses_same_inclusive_duration(self):
        filters = SalesFilters(
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 16),
            sales_channels=("web",),
            financial_statuses=("PAID",),
            currency_codes=("USD",),
        )
        current, previous, previous_filters = build_sales_comparison_period(
            filters, "previous_period"
        )
        self.assertEqual((current.start_date, current.end_date, current.days), (
            date(2026, 8, 10), date(2026, 8, 16), 7
        ))
        self.assertEqual((previous.start_date, previous.end_date, previous.days), (
            date(2026, 8, 3), date(2026, 8, 9), 7
        ))
        self.assertEqual(previous_filters.sales_channels, ("web",))
        self.assertEqual(previous_filters.financial_statuses, ("PAID",))
        self.assertEqual(previous_filters.currency_codes, ("USD",))

    def test_previous_period_handles_fourteen_days(self):
        _current, previous, _filters = build_sales_comparison_period(
            SalesFilters(start_date=date(2026, 8, 1), end_date=date(2026, 8, 14)),
            "previous_period",
        )
        self.assertEqual((previous.start_date, previous.end_date, previous.days), (
            date(2026, 7, 18), date(2026, 7, 31), 14
        ))

    def test_fixed_comparison_windows_use_exact_calendar_days(self):
        filters = SalesFilters(
            start_date=date(2026, 8, 10), end_date=date(2026, 8, 16)
        )
        _current, previous_7, _filters = build_sales_comparison_period(
            filters, "previous_7_days"
        )
        _current, previous_30, _filters = build_sales_comparison_period(
            filters, "previous_30_days"
        )
        self.assertEqual((previous_7.start_date, previous_7.end_date, previous_7.days), (
            date(2026, 8, 3), date(2026, 8, 9), 7
        ))
        self.assertEqual((previous_30.start_date, previous_30.end_date, previous_30.days), (
            date(2026, 7, 11), date(2026, 8, 9), 30
        ))

    def test_comparison_requires_dates_and_uses_strict_allowlist(self):
        with self.assertRaisesRegex(ValueError, "Select both"):
            build_sales_comparison_period(SalesFilters(), "previous_period")
        with self.assertRaisesRegex(ValueError, "Unsupported comparison"):
            build_sales_comparison_period(SalesFilters(), "previous_year")

    def test_zero_baseline_never_returns_infinity(self):
        current = SalesChartResult(
            [SalesChartAggregateRow("2026-08-10", date(2026, 8, 10), Decimal("100"), 1, 2)],
            "USD", Decimal("100"), 1, 2,
        )
        previous = SalesChartResult(
            [SalesChartAggregateRow("2026-08-03", date(2026, 8, 3), Decimal("0"), 1, 0)],
            "USD", Decimal("0"), 1, 0,
        )
        response = SalesService(ComparisonRepositoryStub(current, previous)).get_sales_chart(
            SalesFilters(start_date=date(2026, 8, 10), end_date=date(2026, 8, 16)),
            "processed_date", "revenue", "previous_period",
        )
        self.assertEqual(response.summary.comparison_status, "no_baseline")
        self.assertIsNone(response.summary.percentage_change)
        self.assertEqual(len(response.data), 7)
        self.assertEqual(len(response.comparison_data), 7)

    def test_no_previous_data_preserves_current_chart(self):
        current = SalesChartResult(
            [SalesChartAggregateRow("web", "web", Decimal("100"), 1, 2)],
            "USD", Decimal("100"), 1, 2,
        )
        previous = SalesChartResult([], "USD")
        response = SalesService(ComparisonRepositoryStub(current, previous)).get_sales_chart(
            SalesFilters(start_date=date(2026, 8, 10), end_date=date(2026, 8, 16)),
            "sales_channel", "revenue", "previous_period",
        )
        self.assertTrue(response.has_current_data)
        self.assertFalse(response.has_comparison_data)
        self.assertEqual(response.summary.comparison_status, "no_data")
        self.assertEqual(response.comparison_data, [])

    def test_product_comparison_reuses_current_top_product_ids(self):
        current = SalesChartResult([
            SalesChartAggregateRow("product-a", "A", Decimal("80"), 2, 4),
            SalesChartAggregateRow("product-b", "B", Decimal("50"), 1, 2),
        ], "USD", Decimal("130"), 3, 6)
        previous = SalesChartResult([
            SalesChartAggregateRow("product-b", "B", Decimal("60"), 2, 3),
            SalesChartAggregateRow("product-a", "A", Decimal("40"), 1, 2),
        ], "USD", Decimal("100"), 3, 5)
        repository = ComparisonRepositoryStub(current, previous)
        response = SalesService(repository).get_sales_chart(
            SalesFilters(start_date=date(2026, 8, 10), end_date=date(2026, 8, 16)),
            "product", "revenue", "previous_period",
        )
        self.assertEqual(repository.calls[1][3], ("product-a", "product-b"))
        self.assertEqual({point.id for point in response.comparison_data}, {
            "product-a", "product-b"
        })

    def test_endpoint_rejects_invalid_comparison_with_400(self):
        with self.assertRaises(HTTPException) as context:
            get_sales_chart(
                dimension="processed_date",
                measure="revenue",
                comparison="previous_year",
                filters=SalesFilters(),
                db=object(),
            )
        self.assertEqual(context.exception.status_code, 400)


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class SalesChartPostgresTests(unittest.TestCase):
    def test_supported_matrix_runs_against_current_postgresql_data(self):
        combinations = {
            "processed_date": (
                "revenue",
                "orders",
                "units_sold",
                "average_order_value",
            ),
            "sales_channel": (
                "revenue",
                "orders",
                "units_sold",
                "average_order_value",
            ),
            "product": ("revenue", "orders", "units_sold"),
        }
        with SessionLocal() as db:
            service = SalesService(SalesRepository(db))
            summary = service.get_sales_summary(SalesFilters())
            responses = {
                (dimension, measure): service.get_sales_chart(
                    SalesFilters(), dimension, measure
                )
                for dimension, measures in combinations.items()
                for measure in measures
            }

        date_revenue = responses[("processed_date", "revenue")]
        self.assertAlmostEqual(
            sum(point.value for point in date_revenue.data),
            summary.total_sales,
            places=2,
        )
        self.assertLessEqual(len(responses[("product", "revenue")].data), 5)

    def test_comparison_matrix_and_summaries_reconcile_on_current_data(self):
        with SessionLocal() as db:
            latest = db.scalar(select(func.max(Order.processed_at)))
            self.assertIsNotNone(latest)
            end_date = latest.date()
            filters = SalesFilters(
                start_date=end_date - timedelta(days=6), end_date=end_date
            )
            service = SalesService(SalesRepository(db))
            summary = service.get_sales_summary(filters)
            responses = {
                (dimension, measure): service.get_sales_chart(
                    filters, dimension, measure, "previous_period"
                )
                for dimension, measures in {
                    "processed_date": (
                        "revenue", "orders", "units_sold", "average_order_value"
                    ),
                    "sales_channel": (
                        "revenue", "orders", "units_sold", "average_order_value"
                    ),
                    "product": ("revenue", "orders", "units_sold"),
                }.items()
                for measure in measures
            }

        self.assertAlmostEqual(
            responses[("processed_date", "revenue")].summary.current_value,
            summary.total_sales,
            places=2,
        )
        self.assertEqual(
            responses[("processed_date", "orders")].summary.current_value,
            summary.orders_count,
        )
        self.assertAlmostEqual(
            responses[("processed_date", "average_order_value")]
            .summary.current_value,
            summary.average_order_value,
            places=2,
        )
        product = responses[("product", "revenue")]
        self.assertLessEqual(len(product.data), 5)
        self.assertTrue(
            {point.id for point in product.comparison_data}
            .issubset({point.id for point in product.data})
        )


if __name__ == "__main__":
    unittest.main()
