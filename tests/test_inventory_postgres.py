import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.inventory_repository import InventoryFilters
from app.routers.inventory import get_inventory_kpis, get_inventory_table


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class InventoryPostgresTests(unittest.TestCase):
    def test_product_level_kpis_match_product_table(self):
        with SessionLocal() as db:
            filters = InventoryFilters()
            table = get_inventory_table(
                page=1,
                page_size=100,
                sort_order="asc",
                filters=filters,
                level="product",
                db=db,
                settings=get_settings(),
            )
            kpis = get_inventory_kpis(
                filters=filters,
                level="product",
                db=db,
                settings=get_settings(),
            )

        self.assertEqual(table.level, "product")
        self.assertTrue(all(item.variant is None for item in table.items))
        self.assertTrue(all(item.location is None for item in table.items))
        status_counts = {
            status: sum(item.inventory_status == status for item in table.items)
            for status in ("healthy", "low_stock", "out_of_stock")
        }
        self.assertEqual(kpis.in_stock_products, status_counts["healthy"] + status_counts["low_stock"])
        self.assertEqual(kpis.low_stock_products, status_counts["low_stock"])
        self.assertEqual(kpis.out_of_stock_products, status_counts["out_of_stock"])
        self.assertEqual(kpis.total_inventory_units, table.totals.total_inventory_units)

        if table.items:
            product_id = table.items[0].product_id
            with SessionLocal() as db:
                drilldown_filters = InventoryFilters(product_ids=(product_id,))
                variants = get_inventory_table(
                    page=1,
                    page_size=100,
                    sort_order="asc",
                    filters=drilldown_filters,
                    level="variant",
                    db=db,
                    settings=get_settings(),
                )
                variant_kpis = get_inventory_kpis(
                    filters=drilldown_filters,
                    level="variant",
                    db=db,
                    settings=get_settings(),
                )

            self.assertTrue(
                all(item.product_id == product_id for item in variants.items)
            )
            self.assertEqual(
                variant_kpis.total_inventory_units,
                variants.totals.total_inventory_units,
            )

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
