from types import SimpleNamespace
import unittest

from sqlalchemy.dialects import postgresql

from app.repositories.dashboard_repository import DashboardRepository


class CapturingResult:
    def __init__(self, row=None):
        self.row = row

    def one(self):
        return self.row

    def first(self):
        return self.row


class CapturingSession:
    def __init__(self, row):
        self.row = row
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return CapturingResult(self.row)


class DashboardRepositoryTests(unittest.TestCase):
    def test_inventory_query_uses_documented_boundaries_and_distinct_products(self):
        session = CapturingSession(
            SimpleNamespace(
                products_with_inventory=4,
                low_stock_count=2,
                out_of_stock_count=1,
            )
        )

        result = DashboardRepository(session).get_inventory_health(10)
        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertEqual(result.low_stock_count, 2)
        self.assertIn("BETWEEN 1 AND 10", sql)
        self.assertIn("inventory_quantity = 0", sql)
        self.assertIn("count(distinct", sql.lower())

    def test_top_product_query_has_stable_deterministic_tie_break(self):
        session = CapturingSession(None)

        result = DashboardRepository(session).get_top_selling_product()
        sql = str(
            session.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIsNone(result)
        self.assertIn("GROUP BY order_line_items.product_id", sql)
        self.assertIn("ORDER BY units_sold DESC, product_revenue DESC", sql)
        self.assertIn("order_line_items.product_id ASC", sql)


if __name__ == "__main__":
    unittest.main()
