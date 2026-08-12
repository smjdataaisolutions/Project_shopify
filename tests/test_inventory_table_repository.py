from pathlib import Path
import unittest

from sqlalchemy.dialects import postgresql

from app.db.models import InventoryLevel, Location, ProductVariant
from app.repositories.inventory_repository import InventoryRepository


class InventoryTableRepositoryTests(unittest.TestCase):
    def test_models_expose_verified_inventory_join_columns(self):
        self.assertEqual(ProductVariant.inventory_item_id.name, "inventory_item_id")
        self.assertEqual(InventoryLevel.inventory_item_id.name, "inventory_item_id")
        self.assertEqual(InventoryLevel.location_id.name, "location_id")
        self.assertEqual(Location.id.name, "id")

    def test_table_query_uses_location_available_quantity_and_stable_joins(self):
        statement = InventoryRepository._inventory_table_base_statement()
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("LEFT OUTER JOIN products", sql)
        self.assertIn("LEFT OUTER JOIN inventory", sql)
        self.assertIn(
            "inventory.inventory_item_id = product_variants.inventory_item_id",
            sql,
        )
        self.assertIn("LEFT OUTER JOIN locations", sql)
        self.assertIn("locations.id = inventory.location_id", sql)
        self.assertIn("jsonb_path_query_first", sql)
        self.assertIn("available", sql)
        self.assertNotIn("product_variants.inventory_quantity AS inventory_units", sql)

    def test_inventory_units_sorting_is_applied_before_pagination(self):
        ascending = str(
            InventoryRepository._inventory_table_statement(1, 25, "asc").compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        descending = str(
            InventoryRepository._inventory_table_statement(1, 25, "desc").compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("inventory_units ASC NULLS LAST", ascending)
        self.assertIn("inventory_units DESC NULLS LAST", descending)
        self.assertIn("LIMIT 25 OFFSET 0", ascending)

    def test_sync_and_ddl_store_location_level_available_quantities(self):
        project_root = Path(__file__).resolve().parents[1]
        sync_source = (project_root / "job_conf" / "shpfy_postgre.py").read_text(
            encoding="utf-8"
        )
        ddl_source = (project_root / "ddl" / "ddl.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn('quantities(names: ["available"', sync_source)
        self.assertIn('"inventory_item_id": item["id"]', sync_source)
        self.assertIn('"location_id": location["id"]', sync_source)
        self.assertIn("PRIMARY KEY (inventory_item_id, location_id)", ddl_source)


if __name__ == "__main__":
    unittest.main()
