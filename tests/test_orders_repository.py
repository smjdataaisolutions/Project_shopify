from datetime import date
import unittest

from sqlalchemy.dialects import postgresql

from app.repositories.orders_repository import OrderFilters, OrdersRepository


class OrdersRepositoryTests(unittest.TestCase):
    def test_kpi_query_aggregates_line_items_once_and_applies_filters(self):
        repository = OrdersRepository(db=object())
        statement = repository._apply_filters(
            repository._kpi_statement(),
            OrderFilters(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 17),
                sales_channels=("web", "pos"),
                order_statuses=("cancelled",),
                fulfillment_statuses=("FULFILLED",),
                payment_statuses=("PAID",),
            ),
        )
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("GROUP BY order_line_items.order_id", sql)
        self.assertIn("LEFT OUTER JOIN", sql)
        self.assertIn("count(distinct(orders.id))", sql.lower())
        self.assertIn("sum(order_line_items.quantity)", sql)
        self.assertIn("orders.cancelled_at IS NOT NULL", sql)
        self.assertIn("orders.refunded_at IS NOT NULL", sql)
        self.assertIn("orders.total_refunded > 0", sql)
        self.assertIn("REFUNDED", sql)
        self.assertIn("PARTIALLY_REFUNDED", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sql)
        self.assertIn("orders.processed_at < '2026-08-18'", sql)
        self.assertIn("orders.sales_channel IN ('web', 'pos')", sql)
        self.assertIn("orders.cancelled_at IS NOT NULL", sql)
        self.assertIn("orders.fulfillment_status IN ('FULFILLED')", sql)
        self.assertIn("orders.financial_status IN ('PAID')", sql)

    def test_open_and_all_order_status_filters_use_available_cancellation_data(self):
        repository = OrdersRepository(db=object())
        open_sql = str(
            repository._apply_filters(
                repository._kpi_statement(),
                OrderFilters(order_statuses=("open",)),
            ).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        all_sql = str(
            repository._apply_filters(
                repository._kpi_statement(),
                OrderFilters(order_statuses=("open", "cancelled")),
            ).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("orders.cancelled_at IS NULL", open_sql)
        self.assertNotIn("orders.cancelled_at IS NULL", all_sql)


if __name__ == "__main__":
    unittest.main()
