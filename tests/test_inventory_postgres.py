import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.inventory_repository import InventoryFilters
from app.routers.inventory import get_inventory_kpis


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class InventoryPostgresTests(unittest.TestCase):
    def test_inventory_kpis_use_real_postgresql_and_api_contract(self):
        with SessionLocal() as db:
            payload = get_inventory_kpis(
                filters=InventoryFilters(),
                db=db,
                settings=get_settings(),
            ).model_dump()

        self.assertEqual(
            set(payload),
            {
                "total_inventory_units",
                "in_stock_products",
                "low_stock_products",
                "out_of_stock_products",
                "sell_through_rate",
                "days_of_inventory_remaining",
            },
        )
        self.assertGreaterEqual(payload["total_inventory_units"], 0)
        self.assertGreaterEqual(payload["in_stock_products"], 0)
        self.assertGreaterEqual(payload["low_stock_products"], 0)
        self.assertGreaterEqual(payload["out_of_stock_products"], 0)


if __name__ == "__main__":
    unittest.main()
