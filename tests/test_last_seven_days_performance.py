import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.routing import APIRoute

from app.repositories.dashboard_repository import (
    DailyStorePerformanceResult,
    DailyStorePerformanceRow,
    LastSevenDaysProductMetric,
    OverviewFilters,
    OverviewSalesMetrics,
)
from app.routers.dashboard import router
from app.schemas.dashboard import LastSevenDaysPerformanceResponse
from app.services.dashboard_service import DashboardService


class LastSevenDaysRepositoryStub:
    def __init__(self, sales_results=None):
        self.daily_filters = None
        self.product_filters = None
        self.sales_filters = []
        self.sales_results = sales_results or [
            OverviewSalesMetrics(Decimal("105"), 3, "USD"),
            OverviewSalesMetrics(Decimal("100"), 2, "USD"),
        ]

    def get_daily_store_performance(
        self, page, page_size, sort_by, sort_order, filters
    ):
        self.daily_filters = filters
        return DailyStorePerformanceResult(
            rows=[
                DailyStorePerformanceRow(
                    date=date(2026, 8, 8),
                    total_sales=Decimal("20"),
                    orders=1,
                    units_sold=2,
                ),
                DailyStorePerformanceRow(
                    date=date(2026, 8, 13),
                    total_sales=Decimal("30"),
                    orders=2,
                    units_sold=3,
                ),
            ],
            total_items=2,
            total_sales=Decimal("50"),
            total_orders=3,
            total_units_sold=5,
            currency_code="USD",
        )

    def get_top_products_by_units(self, filters, limit):
        self.product_filters = filters
        return [
            LastSevenDaysProductMetric(
                product_id="product-1",
                product_title="Example product",
                units_sold=5,
                orders=3,
                net_product_sales=Decimal("42.50"),
                currency_code="USD",
            )
        ]

    def get_sales_metrics(self, filters):
        self.sales_filters.append(filters)
        return self.sales_results[len(self.sales_filters) - 1]


class LastSevenDaysPerformanceTests(unittest.TestCase):
    def build(self, today=date(2026, 8, 13), sales_results=None):
        repository = LastSevenDaysRepositoryStub(sales_results)
        response = DashboardService(
            repository,
            low_stock_threshold=10,
            today=lambda: today,
        ).get_last_seven_days_performance(
            OverviewFilters(
                start_date=date(2020, 1, 1),
                end_date=date(2020, 1, 2),
                financial_statuses=("PAID",),
            )
        )
        return repository, response

    def test_periods_are_adjacent_non_overlapping_seven_day_windows(self):
        repository, response = self.build()

        self.assertEqual(response.period.current_start, date(2026, 8, 7))
        self.assertEqual(response.period.current_end, date(2026, 8, 13))
        self.assertEqual(response.period.previous_start, date(2026, 7, 31))
        self.assertEqual(response.period.previous_end, date(2026, 8, 6))
        self.assertEqual(response.period.time_zone, "UTC")
        self.assertEqual(repository.sales_filters[0].financial_statuses, ("PAID",))
        self.assertEqual(repository.sales_filters[1].financial_statuses, ("PAID",))
        self.assertEqual(
            repository.sales_filters[0].start_date,
            datetime(2026, 8, 7, tzinfo=timezone.utc),
        )
        self.assertEqual(
            repository.sales_filters[1].end_date,
            datetime(2026, 8, 6, tzinfo=timezone.utc),
        )

    def test_orders_always_contains_seven_rows_with_zero_dates(self):
        _, response = self.build()

        self.assertEqual(len(response.orders_by_day.items), 7)
        self.assertEqual(response.orders_by_day.total_orders, 3)
        self.assertEqual(response.orders_by_day.items[0].orders, 0)
        self.assertEqual(response.orders_by_day.items[1].orders, 1)
        self.assertEqual(response.orders_by_day.items[-1].units_sold, 3)

    def test_top_products_and_positive_comparison_are_serialized(self):
        _, response = self.build()

        product = response.top_selling_products.items[0]
        self.assertEqual(product.product_id, "product-1")
        self.assertEqual(product.orders, 3)
        self.assertEqual(product.net_product_sales, 42.5)
        comparison = response.total_revenue_comparison
        self.assertEqual(comparison.status, "increase")
        self.assertEqual(comparison.percentage_change, 5.0)

    def test_year_boundary_is_calculated_by_calendar_days(self):
        _, response = self.build(date(2026, 1, 3))
        self.assertEqual(response.period.current_start, date(2025, 12, 28))
        self.assertEqual(response.period.previous_start, date(2025, 12, 21))

    def test_leap_day_and_month_boundary_are_supported(self):
        _, response = self.build(date(2024, 3, 2))
        self.assertEqual(response.period.current_start, date(2024, 2, 25))
        self.assertEqual(response.period.previous_end, date(2024, 2, 24))

    def test_zero_baselines_do_not_produce_infinite_percentage(self):
        zero = OverviewSalesMetrics(Decimal("0"), 0, "USD")
        _, no_change = self.build(sales_results=[zero, zero])
        self.assertEqual(no_change.total_revenue_comparison.status, "no_change")
        self.assertEqual(no_change.total_revenue_comparison.percentage_change, 0.0)

        current = OverviewSalesMetrics(Decimal("10"), 1, "USD")
        _, new_activity = self.build(sales_results=[current, zero])
        self.assertEqual(
            new_activity.total_revenue_comparison.status, "new_activity"
        )
        self.assertIsNone(
            new_activity.total_revenue_comparison.percentage_change
        )

    def test_current_zero_after_previous_sales_is_full_decline(self):
        current = OverviewSalesMetrics(Decimal("0"), 0, "USD")
        previous = OverviewSalesMetrics(Decimal("10"), 1, "USD")
        _, response = self.build(sales_results=[current, previous])
        comparison = response.total_revenue_comparison
        self.assertEqual(comparison.status, "decline")
        self.assertEqual(comparison.percentage_change, -100.0)

    def test_endpoint_does_not_expose_custom_date_parameters(self):
        route = next(
            route for route in router.routes
            if isinstance(route, APIRoute)
            and route.path == "/api/analytics/store-performance/last-seven-days"
        )
        dependency_names = {
            parameter.name for dependency in route.dependant.dependencies
            for parameter in dependency.query_params
        }
        self.assertNotIn("start_date", dependency_names)
        self.assertNotIn("end_date", dependency_names)
        self.assertEqual(route.response_model, LastSevenDaysPerformanceResponse)


if __name__ == "__main__":
    unittest.main()
