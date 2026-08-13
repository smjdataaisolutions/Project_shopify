from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.dashboard_repository import (
    DailyStorePerformanceResult,
    DailyStorePerformanceRow,
    DashboardRepository,
    OverviewFilters,
)
from app.routers.dashboard import get_daily_store_performance, router
from app.schemas.dashboard import DailyStorePerformanceResponse
from app.services.dashboard_service import DashboardService


def compile_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class StubDailyRepository:
    def __init__(self, result):
        self.result = result
        self.call = None

    def get_daily_store_performance(
        self, page, page_size, sort_by, sort_order, filters
    ):
        self.call = (page, page_size, sort_by, sort_order, filters)
        return self.result


class DailyStorePerformanceTests(unittest.TestCase):
    def test_page_query_defaults_to_date_descending_and_paginates_daily_rows(self):
        daily = DashboardRepository(
            db=object()
        )._daily_store_performance_statement().subquery()
        statement = DashboardRepository._daily_store_performance_page_statement(
            daily, 2, 10, "date", "desc"
        )
        sql = compile_sql(statement)

        self.assertIn("ORDER BY", sql)
        self.assertIn("date DESC", sql)
        self.assertIn("LIMIT 10 OFFSET 10", sql)

        aov_sql = compile_sql(
            DashboardRepository._daily_store_performance_page_statement(
                daily, 1, 10, "average_order_value", "asc"
            )
        )
        self.assertIn("total_sales / CAST(nullif", aov_sql)
        self.assertIn("ASC", aov_sql)

        for sort_by in (
            "date",
            "total_sales",
            "orders",
            "units_sold",
            "average_order_value",
        ):
            for sort_order in ("asc", "desc"):
                with self.subTest(sort_by=sort_by, sort_order=sort_order):
                    sorted_sql = compile_sql(
                        DashboardRepository._daily_store_performance_page_statement(
                            daily, 1, 10, sort_by, sort_order
                        )
                    )
                    self.assertIn(f" {sort_order.upper()}", sorted_sql)

    def test_query_groups_processed_date_and_preaggregates_multiple_line_items(self):
        filters = OverviewFilters(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 12),
            financial_statuses=("PAID",),
            fulfillment_statuses=("FULFILLED",),
            sales_channels=("web",),
        )
        sql = compile_sql(
            DashboardRepository(db=object())._daily_store_performance_statement(
                filters
            )
        )

        self.assertIn("timezone('UTC', orders.processed_at)", sql)
        self.assertIn("GROUP BY order_line_items.order_id", sql)
        self.assertIn("count(distinct", sql.lower())
        self.assertIn("sum(order_line_items.unit_price * order_line_items.quantity)", sql)
        self.assertIn("sum(order_line_items.quantity)", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sql)
        self.assertIn("orders.processed_at < '2026-08-13'", sql)
        self.assertIn("orders.financial_status IN ('PAID')", sql)
        self.assertIn("orders.fulfillment_status IN ('FULFILLED')", sql)
        self.assertIn("orders.sales_channel IN ('web')", sql)

    def test_service_calculates_daily_and_complete_result_aov(self):
        repository = StubDailyRepository(
            DailyStorePerformanceResult(
                rows=[
                    DailyStorePerformanceRow(
                        date(2026, 8, 12), Decimal("245.00"), 2, 5
                    ),
                    DailyStorePerformanceRow(
                        date(2026, 8, 11), Decimal("55.00"), 1, 2
                    ),
                ],
                total_items=12,
                total_sales=Decimal("900.00"),
                total_orders=6,
                total_units_sold=18,
                currency_code="USD",
            )
        )
        filters = OverviewFilters(financial_statuses=("PAID",))

        response = DashboardService(repository, 10).get_daily_store_performance(
            2, 10, "date", "desc", filters
        )

        self.assertEqual(
            repository.call, (2, 10, "date", "desc", filters)
        )
        self.assertEqual(response.items[0].average_order_value, 122.5)
        self.assertEqual(response.summary.total_sales, 900.0)
        self.assertEqual(response.summary.orders, 6)
        self.assertEqual(response.summary.units_sold, 18)
        self.assertEqual(response.summary.average_order_value, 150.0)
        self.assertEqual(response.pagination.total_pages, 2)
        self.assertEqual(response.pagination.total_items, 12)

    def test_zero_order_aov_is_zero(self):
        repository = StubDailyRepository(
            DailyStorePerformanceResult(
                rows=[],
                total_items=0,
                total_sales=Decimal("0"),
                total_orders=0,
                total_units_sold=0,
                currency_code=None,
            )
        )

        response = DashboardService(repository, 10).get_daily_store_performance(
            1, 10, "date", "desc", OverviewFilters()
        )

        self.assertEqual(response.summary.average_order_value, 0.0)
        self.assertEqual(response.pagination.total_pages, 0)

    @patch("app.routers.dashboard.DashboardService.get_daily_store_performance")
    def test_api_uses_typed_contract_and_forwards_sorting(self, get_daily):
        get_daily.return_value = DailyStorePerformanceResponse(
            currency_code="USD",
            items=[],
            summary={
                "total_sales": 0,
                "orders": 0,
                "units_sold": 0,
                "average_order_value": 0,
            },
            pagination={
                "page": 1,
                "page_size": 10,
                "total_items": 0,
                "total_pages": 0,
            },
        )
        filters = OverviewFilters()

        response = get_daily_store_performance(
            page=1,
            page_size=10,
            sort_by="total_sales",
            sort_order="asc",
            filters=filters,
            db=object(),
        )

        get_daily.assert_called_once_with(
            1, 10, "total_sales", "asc", filters
        )
        self.assertEqual(response.pagination.total_items, 0)

    def test_route_uses_documented_path_and_response_model(self):
        route = next(
            route
            for route in router.routes
            if route.path == "/api/analytics/store-performance/daily"
        )
        self.assertEqual(route.response_model, DailyStorePerformanceResponse)
        self.assertIn("GET", route.methods)

    @patch("app.routers.dashboard.DashboardRepository.get_daily_store_performance")
    def test_api_returns_retryable_sanitized_error(self, get_daily):
        get_daily.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_daily_store_performance(
                page=1,
                page_size=10,
                sort_by="date",
                sort_order="desc",
                filters=OverviewFilters(),
                db=object(),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve daily store performance.",
        )


if __name__ == "__main__":
    unittest.main()
