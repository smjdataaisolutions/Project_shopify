import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.inventory_repository import InventoryRepository
from app.services.inventory_service import InventoryService


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class InventoryTablePostgresTests(unittest.TestCase):
    def test_reads_variant_location_rows_and_preserves_inventory_conditions(self):
        with SessionLocal() as db:
            service = InventoryService(
                InventoryRepository(db),
                get_settings().low_stock_threshold,
            )
            response = service.get_inventory_table(page=1, page_size=100)
            kpis = service.get_kpis()

        keys = [(item.variant_id, item.location_id) for item in response.items]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(response.pagination.total_items, len(response.items))
        self.assertTrue(any(item.inventory_units == 0 for item in response.items))
        self.assertTrue(any((item.inventory_units or 0) < 0 for item in response.items))
        self.assertTrue(any(not item.inventory_tracked for item in response.items))
        self.assertTrue(all(item.product_variant_name for item in response.items))
        self.assertEqual(
            response.totals.total_inventory_units,
            kpis.total_inventory_units,
        )


if __name__ == "__main__":
    unittest.main()
