import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.inventory_repository import InventoryFilters
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
        self.assertTrue(all(item.product for item in response.items))
        self.assertTrue(all(item.variant for item in response.items))
        self.assertEqual(
            response.totals.total_inventory_units,
            kpis.total_inventory_units,
        )
        self.assertEqual(
            sum(
                item.inventory_tracked
                and item.inventory_units is not None
                and item.inventory_units > 0
                for item in response.items
            ),
            kpis.in_stock_products,
        )
        self.assertEqual(
            sum(item.inventory_status == "low_stock" for item in response.items),
            kpis.low_stock_products,
        )
        self.assertEqual(
            sum(
                item.inventory_status == "out_of_stock"
                for item in response.items
            ),
            kpis.out_of_stock_products,
        )

    def test_location_filter_keeps_table_totals_and_kpis_in_sync(self):
        with SessionLocal() as db:
            service = InventoryService(
                InventoryRepository(db),
                get_settings().low_stock_threshold,
            )
            options = service.get_filter_options()
            self.assertTrue(options.locations)
            self.assertTrue(options.vendors)
            self.assertIsNotNone(options.date_range.latest_inventory_sync_at)

            location_id = options.locations[0].id
            filters = InventoryFilters(location_ids=(location_id,))
            response = service.get_inventory_table(
                page=1,
                page_size=100,
                filters=filters,
            )
            kpis = service.get_kpis(filters)

        self.assertTrue(
            all(item.location_id == location_id for item in response.items)
        )
        self.assertEqual(
            response.totals.total_inventory_units,
            kpis.total_inventory_units,
        )


if __name__ == "__main__":
    unittest.main()
