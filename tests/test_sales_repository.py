from datetime import date
import unittest

from sqlalchemy.dialects import postgresql

from app.repositories.sales_repository import SalesRepository


class SalesRepositoryTests(unittest.TestCase):
    def test_sales_metrics_reuses_sal_001_formulas_and_processed_date_filters(self):
        repository = SalesRepository(db=object())
        statement = repository._with_date_filters(
            repository._sales_metrics_statement(),
            date(2026, 8, 1),
            date(2026, 8, 10),
        )
        sql = str(statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ))

        self.assertIn("sum(orders.subtotal_price)", sql)
        self.assertIn("sum(orders.total_discount)", sql)
        self.assertIn("sum(orders.total_price)", sql)
        self.assertIn("orders.financial_status IN ('REFUNDED', 'PARTIALLY_REFUNDED')", sql)
        self.assertIn("orders.cancelled_at IS NOT NULL", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sql)
        self.assertIn("orders.processed_at < '2026-08-11'", sql)

    def test_action_export_uses_contributing_orders_products_and_date_filters(self):
        repository = SalesRepository(db=object())
        statement = repository._with_date_filters(
            repository._action_export_statement(),
            date(2026, 8, 1),
            date(2026, 8, 10),
        )
        sql = str(statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ))

        self.assertIn("LEFT OUTER JOIN order_line_items", sql)
        self.assertIn("orders.total_refunded", sql)
        self.assertIn("orders.refund_reason", sql)
        self.assertIn("orders.financial_status IN ('REFUNDED', 'PARTIALLY_REFUNDED')", sql)
        self.assertIn("orders.cancelled_at IS NOT NULL", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sql)
        self.assertIn("orders.processed_at < '2026-08-11'", sql)


if __name__ == "__main__":
    unittest.main()
