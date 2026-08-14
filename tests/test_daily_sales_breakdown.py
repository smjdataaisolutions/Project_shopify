from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from app.repositories.sales_repository import (
    DailySalesBreakdownResult,
    DailySalesBreakdownRow,
    SalesFilters,
    SalesRepository,
)
from app.routers.sales import get_daily_sales_breakdown, router
from app.schemas.sales import DailySalesBreakdownResponse
from app.services.sales_service import SalesService


class StubRepository:
    def __init__(self, result):
        self.result = result
        self.arguments = None

    def get_daily_breakdown(
        self, filters, page, page_size, sort_by, sort_direction
    ):
        self.arguments = (filters, page, page_size, sort_by, sort_direction)
        return self.result


def breakdown_result():
    return DailySalesBreakdownResult(
        rows=[
            DailySalesBreakdownRow(
                date=date(2026, 8, 12),
                gross_sales=Decimal("250.00"),
                discounts=Decimal("10.00"),
                returns_refunds=Decimal("20.00"),
                net_sales=Decimal("220.00"),
                shipping=Decimal("7.00"),
                tax=Decimal("11.00"),
                total_sales=Decimal("238.00"),
                orders=2,
            )
        ],
        total_items=3,
        gross_sales=Decimal("440.00"),
        discounts=Decimal("16.00"),
        returns_refunds=Decimal("20.00"),
        net_sales=Decimal("404.00"),
        shipping=Decimal("12.00"),
        tax=Decimal("21.00"),
        total_sales=Decimal("437.00"),
        orders=4,
        currency_code="USD",
    )


class DailySalesBreakdownTests(unittest.TestCase):
    def test_daily_query_uses_processed_utc_date_and_order_level_kpi_fields(self):
        repository = SalesRepository(object())
        statement = repository._daily_breakdown_statement(
            SalesFilters(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 12),
                sales_channels=("web",),
                financial_statuses=("PAID",),
                currency_codes=("USD",),
            )
        )
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()

        self.assertIn("timezone('utc', orders.processed_at)", sql)
        self.assertIn("sum(orders.subtotal_price)", sql)
        self.assertIn("sum(orders.total_discount)", sql)
        self.assertIn("sum(orders.total_refunded)", sql)
        self.assertIn("sum(orders.total_shipping)", sql)
        self.assertIn("sum(orders.total_tax)", sql)
        self.assertIn("sum(orders.total_price)", sql)
        self.assertIn("count(distinct(orders.id))", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sql)
        self.assertIn("orders.processed_at < '2026-08-13'", sql)
        self.assertIn("orders.sales_channel in ('web')", sql)
        self.assertIn("orders.financial_status in ('paid')", sql)
        self.assertIn("orders.currency_code in ('usd')", sql)
        self.assertNotIn("join order_line_items", sql)

    def test_order_level_source_prevents_multi_related_record_multiplication(self):
        repository = SalesRepository(object())
        sql = str(
            repository._daily_breakdown_statement(SalesFilters()).compile(
                dialect=postgresql.dialect()
            )
        ).lower()

        self.assertNotIn("order_line_items", sql)
        self.assertNotIn("refund_line", sql)
        self.assertIn("count(distinct(orders.id))", sql)

    def test_every_column_sorts_before_pagination_with_stable_date_tie_break(self):
        repository = SalesRepository(object())
        daily = repository._daily_breakdown_statement(SalesFilters()).subquery()
        columns = (
            "date",
            "gross_sales",
            "discounts",
            "returns_refunds",
            "net_sales",
            "shipping",
            "tax",
            "total_sales",
            "orders",
            "average_order_value",
        )
        for column in columns:
            with self.subTest(column=column):
                statement = repository._daily_breakdown_page_statement(
                    daily, 2, 10, column, "desc"
                )
                sql = str(statement.compile(dialect=postgresql.dialect())).lower()
                self.assertIn("order by", sql)
                self.assertIn("limit", sql)
                self.assertIn("offset", sql)
                self.assertIn("date desc", sql)

    def test_service_recalculates_row_and_complete_result_aov(self):
        repository = StubRepository(breakdown_result())
        filters = SalesFilters(start_date=date(2026, 8, 1))
        response = SalesService(repository).get_daily_breakdown(
            filters, 2, 2, "gross_sales", "asc"
        )

        self.assertEqual(response.items[0].average_order_value, 119.0)
        self.assertEqual(response.summary.average_order_value, 109.25)
        self.assertEqual(response.summary.net_sales, 404.0)
        self.assertEqual(response.pagination.total_items, 3)
        self.assertEqual(response.pagination.total_pages, 2)
        self.assertEqual(response.sorting.sort_by, "gross_sales")
        self.assertEqual(repository.arguments, (filters, 2, 2, "gross_sales", "asc"))

    def test_service_handles_zero_orders_without_division_error(self):
        result = breakdown_result()
        result = DailySalesBreakdownResult(
            **{**result.__dict__, "rows": [], "total_items": 0, "orders": 0}
        )
        response = SalesService(StubRepository(result)).get_daily_breakdown(
            SalesFilters(), 1, 10, "date", "desc"
        )

        self.assertEqual(response.items, [])
        self.assertEqual(response.summary.average_order_value, 0.0)
        self.assertEqual(response.pagination.total_pages, 0)

    @patch("app.routers.sales.SalesRepository.get_daily_breakdown")
    def test_api_contract_and_filter_forwarding(self, get_breakdown):
        get_breakdown.return_value = breakdown_result()
        filters = SalesFilters(financial_statuses=("PAID",))
        response = get_daily_sales_breakdown(
            page=1,
            page_size=10,
            sort_by="date",
            sort_direction="desc",
            filters=filters,
            db=object(),
        )

        self.assertEqual(response.items[0].date, date(2026, 8, 12))
        self.assertEqual(response.summary.orders, 4)
        self.assertIs(get_breakdown.call_args.args[0], filters)
        route = next(
            route
            for route in router.routes
            if route.path == "/api/sales/daily-breakdown"
        )
        self.assertEqual(route.response_model, DailySalesBreakdownResponse)
        self.assertIn("GET", route.methods)


if __name__ == "__main__":
    unittest.main()
