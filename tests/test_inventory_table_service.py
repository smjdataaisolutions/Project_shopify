import unittest
import csv
import io

from app.repositories.inventory_repository import (
    InventoryFilters,
    InventoryTableResult,
    InventoryTableRow,
)
from app.services.inventory_service import InventoryService


class StubInventoryTableRepository:
    def __init__(self, rows, total_items=None, total_inventory_units=0):
        self.rows = rows
        self.total_items = len(rows) if total_items is None else total_items
        self.total_inventory_units = total_inventory_units
        self.call = None

    def get_inventory_table(
        self, page, page_size, sort_order, filters, low_stock_threshold
    ):
        self.call = (
            page,
            page_size,
            sort_order,
            filters,
            low_stock_threshold,
        )
        return InventoryTableResult(
            self.rows,
            self.total_items,
            self.total_inventory_units,
        )

    def get_inventory_table_export(
        self, sort_order, filters, low_stock_threshold
    ):
        self.call = (sort_order, filters, low_stock_threshold)
        return self.rows


def make_row(
    *,
    variant_id="variant-1",
    location_id="location-1",
    product_title="Classic T-Shirt",
    variant_title="Small",
    inventory_units=18,
    location_name="Main Warehouse",
    inventory_location_name="Stored Warehouse",
    inventory_tracked=True,
):
    return InventoryTableRow(
        variant_id=variant_id,
        location_id=location_id,
        product_title=product_title,
        variant_title=variant_title,
        inventory_units=inventory_units,
        location_name=location_name,
        inventory_location_name=inventory_location_name,
        inventory_tracked=inventory_tracked,
    )


class InventoryTableServiceTests(unittest.TestCase):
    def test_exports_all_displayed_columns_in_requested_order(self):
        repository = StubInventoryTableRepository(
            [
                make_row(inventory_units=-1),
                make_row(
                    variant_id="variant-2",
                    inventory_units=None,
                    location_name=None,
                    inventory_location_name=None,
                    inventory_tracked=False,
                ),
            ]
        )

        export = InventoryService(repository, 10).get_inventory_table_export(
            "desc"
        )
        records = list(csv.DictReader(io.StringIO(export.content)))

        self.assertEqual(repository.call, ("desc", InventoryFilters(), 10))
        self.assertEqual(export.filename, "inventory-details.csv")
        self.assertEqual(
            list(records[0]),
            [
                "Product",
                "Variant",
                "Inventory Units",
                "Inventory Status",
                "Location",
            ],
        )
        self.assertEqual(records[0]["Inventory Status"], "Negative inventory")
        self.assertEqual(records[1]["Inventory Units"], "")
        self.assertEqual(records[1]["Inventory Status"], "Untracked")
        self.assertEqual(records[1]["Location"], "Not assigned")

    def test_formats_names_locations_and_pagination(self):
        repository = StubInventoryTableRepository(
            [
                make_row(),
                make_row(
                    variant_id="variant-2",
                    location_id="location-2",
                    variant_title="Default Title",
                    location_name=None,
                ),
            ],
            total_items=27,
            total_inventory_units=125,
        )

        response = InventoryService(repository, 10).get_inventory_table(2, 25)

        self.assertEqual(
            repository.call,
            (2, 25, "asc", InventoryFilters(), 10),
        )
        self.assertEqual(response.items[0].product, "Classic T-Shirt")
        self.assertEqual(response.items[0].variant, "Small")
        self.assertEqual(response.items[1].product, "Classic T-Shirt")
        self.assertEqual(response.items[1].variant, "Default")
        self.assertEqual(response.items[1].location, "Stored Warehouse")
        self.assertEqual(response.pagination.total_pages, 2)
        self.assertEqual(response.totals.total_inventory_units, 125)

    def test_preserves_quantities_and_assigns_backend_statuses(self):
        rows = [
            make_row(variant_id="healthy", inventory_units=11),
            make_row(variant_id="low-one", inventory_units=1),
            make_row(variant_id="low-threshold", inventory_units=10),
            make_row(variant_id="zero", inventory_units=0),
            make_row(variant_id="negative", inventory_units=-1),
            make_row(variant_id="unknown", inventory_units=None),
            make_row(variant_id="untracked", inventory_units=0, inventory_tracked=False),
        ]

        response = InventoryService(
            StubInventoryTableRepository(rows), 10
        ).get_inventory_table(1, 25)

        self.assertEqual(
            {item.variant_id: (item.inventory_units, item.inventory_status) for item in response.items},
            {
                "healthy": (11, "healthy"),
                "low-one": (1, "low_stock"),
                "low-threshold": (10, "low_stock"),
                "zero": (0, "out_of_stock"),
                "negative": (-1, "negative"),
                "unknown": (None, "unknown"),
                "untracked": (0, "untracked"),
            },
        )

    def test_handles_missing_names_location_tracking_and_empty_result(self):
        response = InventoryService(
            StubInventoryTableRepository(
                [
                    make_row(
                        product_title=" ",
                        variant_title=None,
                        location_name=" ",
                        inventory_location_name=None,
                        inventory_tracked=None,
                        inventory_units=None,
                    )
                ]
            ),
            10,
        ).get_inventory_table(1, 25)

        self.assertEqual(response.items[0].product, "Unnamed product")
        self.assertEqual(response.items[0].variant, "Unnamed variant")
        self.assertIsNone(response.items[0].location)
        self.assertFalse(response.items[0].inventory_tracked)
        self.assertEqual(response.items[0].inventory_status, "untracked")

        empty = InventoryService(
            StubInventoryTableRepository([], total_items=0), 10
        ).get_inventory_table(1, 25)
        self.assertEqual(empty.items, [])
        self.assertEqual(empty.pagination.total_pages, 0)


if __name__ == "__main__":
    unittest.main()
