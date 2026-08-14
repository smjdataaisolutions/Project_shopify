from datetime import date
from pathlib import Path
import unittest

from sqlalchemy.dialects import postgresql

from app.db.models import Order
from app.repositories.sales_repository import SalesFilters, SalesRepository


class SalesRepositoryTests(unittest.TestCase):
    def test_order_model_exposes_postgresql_sales_channel(self):
        self.assertEqual(Order.sales_channel.name, "sales_channel")
        self.assertTrue(Order.sales_channel.nullable)

    def test_shopify_sync_maps_source_name_to_sales_channel(self):
        project_root = Path(__file__).resolve().parents[1]
        sync_source = (project_root / "job_conf" / "shpfy_postgre.py").read_text(
            encoding="utf-8"
        )
        ddl_source = (project_root / "ddl" / "ddl.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn("sourceName", sync_source)
        self.assertIn('"sales_channel": order.get("sourceName")', sync_source)
        self.assertIn("sales_channel TEXT", sync_source)
        self.assertIn("sales_channel TEXT", ddl_source)

    def test_sales_metrics_reuses_sal_001_formulas_and_processed_date_filters(self):
        repository = SalesRepository(db=object())
        statement = repository._apply_filters(
            repository._sales_metrics_statement(),
            SalesFilters(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 10),
                sales_channels=("web", "pos"),
                financial_statuses=("PAID",),
                currency_codes=("USD",),
            ),
        )
        sql = str(statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ))

        self.assertIn("sum(orders.subtotal_price)", sql)
        self.assertIn("sum(orders.total_discount)", sql)
        self.assertIn("sum(orders.total_refunded)", sql)
        self.assertIn("sum(orders.total_price)", sql)
        self.assertIn("count(distinct(orders.id))", sql.lower())
        self.assertIn("orders.processed_at IS NOT NULL", sql)
        self.assertIn("orders.financial_status IN ('REFUNDED', 'PARTIALLY_REFUNDED')", sql)
        self.assertIn("orders.cancelled_at IS NOT NULL", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sql)
        self.assertIn("orders.processed_at < '2026-08-11'", sql)
        self.assertIn("orders.sales_channel IN ('web', 'pos')", sql)
        self.assertIn("orders.financial_status IN ('PAID')", sql)
        self.assertIn("orders.currency_code IN ('USD')", sql)
        self.assertIn("shopify_sync_state.last_successful_sync_at", sql)
        self.assertIn("shopify_sync_state.source = 'shopify'", sql)

    def test_action_export_uses_contributing_orders_products_and_date_filters(self):
        repository = SalesRepository(db=object())
        statement = repository._apply_filters(
            repository._action_export_statement(),
            SalesFilters(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 10),
                sales_channels=("web",),
                financial_statuses=("REFUNDED",),
                currency_codes=("USD",),
            ),
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
        self.assertIn("orders.sales_channel IN ('web')", sql)
        self.assertIn("orders.currency_code IN ('USD')", sql)


if __name__ == "__main__":
    unittest.main()
