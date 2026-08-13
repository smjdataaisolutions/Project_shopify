import unittest
from datetime import date
from decimal import Decimal

from sqlalchemy.dialects import postgresql

from app.repositories.dashboard_repository import DashboardRepository, OverviewFilters


class CapturingResult:
    def __init__(self, row):
        self.row = row

    def one(self):
        return self.row

    def all(self):
        return self.row


class CapturingSession:
    def __init__(self, row):
        self.row = row
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return CapturingResult(self.row)


class Row:
    products_with_inventory = 4
    low_stock_count = 2
    out_of_stock_count = 1


class AffectedProductRow:
    product_id = "product-1"
    product_title = "Example product"
    out_of_stock = 1
    low_stock_quantity = 4


class DashboardRepositoryTests(unittest.TestCase):
    def test_daily_grouping_uses_explicit_utc_calendar_date(self):
        statement = DashboardRepository(object())._daily_store_performance_statement()
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()

        self.assertIn("timezone('utc', orders.processed_at)", sql)

    def test_product_net_sales_groups_by_product_and_allocates_order_adjustments(self):
        statement = DashboardRepository(object())._product_net_sales_statement(
            OverviewFilters(financial_statuses=("PAID",))
        )
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()

        self.assertIn("group by", sql)
        self.assertIn("product_id", sql)
        self.assertIn("total_discount", sql)
        self.assertIn("total_refunded", sql)
        self.assertIn("orders.financial_status in ('paid')", sql)
        self.assertIn("order_gross", sql)
        self.assertIn("count(distinct", sql)

    def test_top_products_rank_by_units_sales_and_product_id_with_limit(self):
        session = CapturingSession(
            [("product-1", "Example", 5, 3, Decimal("42"), "USD")]
        )

        rows = DashboardRepository(session).get_top_products_by_units(
            OverviewFilters(start_date=date(2026, 8, 7)),
            limit=5,
        )
        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()

        self.assertEqual(rows[0].orders, 3)
        self.assertIn("order by", sql)
        self.assertIn("units_sold desc", sql)
        self.assertIn("net_product_sales desc", sql)
        self.assertIn("product_id asc", sql)
        self.assertIn("limit 5", sql)

    def test_inventory_query_uses_postgresql_distinct_product_aggregates(self):
        session = CapturingSession(Row())

        metrics = DashboardRepository(session).get_inventory_health(10)
        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertEqual(metrics.low_stock_count, 2)
        self.assertEqual(metrics.out_of_stock_count, 1)
        self.assertIn("count(distinct", sql.lower())
        self.assertIn("BETWEEN 1 AND 10", sql)
        self.assertIn("inventory_quantity = 0", sql)

    def test_inventory_export_query_targets_only_requested_variants(self):
        session = CapturingSession(
            [("product-1", "Example", None, None, 0, None, 4)]
        )

        rows = DashboardRepository(session).get_inventory_action_export_rows(
            "inventory_out_of_stock",
            10,
            OverviewFilters(start_date=date(2026, 8, 1)),
        )
        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertEqual(rows[0].product_id, "product-1")
        self.assertIn("product_variants.inventory_quantity = 0", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sql)

    def test_sales_export_query_reuses_overview_filters(self):
        session = CapturingSession(
            [("order-1", "Example", 2, Decimal("40"), Decimal("5"), Decimal("35"))]
        )

        rows = DashboardRepository(session).get_sales_action_export_rows(
            OverviewFilters(financial_statuses=("PAID",))
        )
        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertEqual(rows[0].net_sales, Decimal("35"))
        self.assertIn("orders.financial_status IN ('PAID')", sql)

    def test_affected_products_query_returns_one_status_per_product(self):
        session = CapturingSession([AffectedProductRow()])

        products = DashboardRepository(session).get_affected_inventory_products(10)
        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].product_id, "product-1")
        self.assertTrue(products[0].is_out_of_stock)
        self.assertEqual(products[0].low_stock_quantity, 4)
        self.assertIn("LEFT OUTER JOIN products", sql)
        self.assertIn("HAVING", sql)
        self.assertIn("BETWEEN 1 AND 10", sql)


if __name__ == "__main__":
    unittest.main()
