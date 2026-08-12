import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.repositories.inventory_repository import InventoryFilters, InventoryRepository


def compile_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class InventoryFilterRepositoryTests(unittest.TestCase):
    def test_table_query_combines_categories_and_ors_values_within_category(self):
        filters = InventoryFilters(
            location_ids=("location-1", "location-2"),
            vendors=("Acme", "Zen"),
            inventory_tracked=True,
            inventory_statuses=("low_stock", "out_of_stock"),
        )

        sql = compile_sql(
            InventoryRepository._inventory_table_base_statement(filters, 10)
        )

        self.assertIn("inventory.location_id IN ('location-1', 'location-2')", sql)
        self.assertIn("btrim(products.vendor) IN ('Acme', 'Zen')", sql)
        self.assertIn("product_variants.inventory_tracked IS true", sql)
        self.assertIn("IN ('low_stock', 'out_of_stock')", sql)
        self.assertIn("jsonb_path_query_first", sql)

    def test_filtered_kpis_count_items_in_the_same_location_inventory_scope(self):
        sql = compile_sql(
            InventoryRepository._inventory_metrics_statement(
                10,
                InventoryFilters(location_ids=("location-1",)),
            )
        )

        self.assertIn("inventory.location_id IN ('location-1')", sql)
        self.assertIn("anon_2.inventory_tracked IS true", sql)
        self.assertNotIn("GROUP BY anon_2.product_id", sql)

    def test_filter_options_are_loaded_from_postgresql_and_cleaned(self):
        db = MagicMock()
        locations = MagicMock()
        locations.all.return_value = [SimpleNamespace(id="location-1", name=" Main ")]
        vendor_execution = MagicMock()
        vendor_execution.scalars.return_value.all.return_value = ["Acme"]
        db.execute.side_effect = [locations, vendor_execution]
        latest = SimpleNamespace(isoformat=lambda: "2026-08-07T11:35:21+05:30")
        db.scalar.return_value = latest

        options = InventoryRepository(db).get_filter_options()

        self.assertEqual(options.locations[0].name, "Main")
        self.assertEqual(options.vendors, ["Acme"])
        self.assertIs(options.latest_inventory_sync_at, latest)
        self.assertEqual(db.execute.call_count, 2)


if __name__ == "__main__":
    unittest.main()
