from datetime import date
import unittest

from sqlalchemy.dialects import postgresql

from app.repositories.inventory_repository import InventoryFilters, InventoryRepository


def compile_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class InventoryRepositoryTests(unittest.TestCase):
    def test_product_query_aggregates_then_applies_inventory_status(self):
        statement = InventoryRepository._inventory_table_base_statement(
            InventoryFilters(inventory_statuses=("low_stock",)),
            10,
            "product",
        )
        sql = compile_sql(statement)

        self.assertIn("GROUP BY", sql)
        self.assertIn("product_id", sql)
        self.assertIn("sum(", sql)
        self.assertIn("inventory_tracked", sql)
        self.assertIn("low_stock", sql)
        self.assertIn("NULL AS variant_title", sql)

    def test_inventory_query_counts_tracked_variant_location_items(self):
        sql = compile_sql(InventoryRepository._inventory_metrics_statement(10))

        self.assertIn("LEFT OUTER JOIN inventory", sql)
        self.assertIn("jsonb_path_query_first", sql)
        self.assertIn("inventory_tracked IS true", sql)
        self.assertIn("inventory_units IS NOT NULL", sql)
        self.assertNotIn("GROUP BY product_variants.product_id", sql)
        self.assertIn("sum(greatest", sql)
        self.assertIn("inventory_units > 0", sql)
        self.assertIn("inventory_units BETWEEN 1 AND 10", sql)
        self.assertIn("inventory_units = 0", sql)

    def test_units_sold_query_uses_positive_units_and_inclusive_period(self):
        sql = compile_sql(
            InventoryRepository._units_sold_statement(
                date(2026, 7, 13), date(2026, 8, 11)
            )
        )

        self.assertIn("JOIN orders", sql)
        self.assertIn("order_line_items.quantity > 0", sql)
        self.assertIn("orders.processed_at >= '2026-07-13'", sql)
        self.assertIn("orders.processed_at < '2026-08-12'", sql)


if __name__ == "__main__":
    unittest.main()
