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



if __name__ == "__main__":
    unittest.main()
