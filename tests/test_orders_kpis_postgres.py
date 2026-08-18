import os
import unittest

from app.db.session import SessionLocal
from app.repositories.orders_repository import OrdersRepository
from app.services.orders_service import OrdersService


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class OrdersKpiPostgresTests(unittest.TestCase):
    def test_configured_postgresql_returns_valid_order_kpis(self):
        with SessionLocal() as db:
            response = OrdersService(OrdersRepository(db)).get_kpis()

        self.assertGreaterEqual(response.total_orders, 0)
        self.assertGreaterEqual(response.units_ordered, 0)
        self.assertGreaterEqual(response.cancelled_orders, 0)
        self.assertGreaterEqual(response.refunded_orders, 0)
        self.assertGreaterEqual(response.fulfillment_rate, 0.0)

    def test_configured_postgresql_returns_reconciling_order_charts(self):
        with SessionLocal() as db:
            service = OrdersService(OrdersRepository(db))
            kpis = service.get_kpis()
            charts = service.get_charts()

        fulfillment = {point.status: point.orders for point in charts.fulfillment_status}
        self.assertEqual(fulfillment["Fulfilled"], kpis.fulfilled_orders)
        self.assertEqual(fulfillment["Unfulfilled"], kpis.unfulfilled_orders)
        self.assertEqual(
            fulfillment["Partially Fulfilled"], kpis.partially_fulfilled_orders
        )
        self.assertEqual(
            sum(point.orders for point in charts.orders_by_sales_channel),
            kpis.total_orders,
        )
        self.assertEqual(
            sum(point.orders for point in charts.order_status_distribution),
            kpis.total_orders,
        )



if __name__ == "__main__":
    unittest.main()
