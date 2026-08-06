import unittest

from sqlalchemy.dialects import postgresql

from app.repositories.dashboard_repository import DashboardRepository


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
