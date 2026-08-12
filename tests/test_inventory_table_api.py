from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.inventory_repository import (
    InventoryTableResult,
    InventoryTableRow,
)
from app.routers.inventory import (
    download_inventory_table,
    get_inventory_table,
    router,
)
from app.schemas.inventory import InventoryTableResponse
from app.services.inventory_service import InventoryTableCsvExport


class InventoryTableApiTests(unittest.TestCase):
    @patch("app.routers.inventory.InventoryService.get_inventory_table_export")
    def test_download_returns_complete_csv_attachment(self, get_export):
        get_export.return_value = InventoryTableCsvExport(
            filename="inventory-details.csv",
            content="Product Variant Name,Inventory Units\r\nShirt,18\r\n",
        )

        response = download_inventory_table(
            sort_order="desc",
            db=object(),
            settings=SimpleNamespace(low_stock_threshold=10),
        )

        get_export.assert_called_once_with("desc")
        self.assertTrue(response.media_type.startswith("text/csv"))
        self.assertIn("attachment;", response.headers["content-disposition"])
        self.assertIn(b"Shirt,18", response.body)

    @patch("app.routers.inventory.InventoryRepository.get_inventory_table")
    def test_endpoint_returns_typed_paginated_response(self, get_table):
        get_table.return_value = InventoryTableResult(
            rows=[
                InventoryTableRow(
                    variant_id="variant-1",
                    location_id="location-1",
                    product_title="Classic T-Shirt",
                    variant_title="Small",
                    inventory_units=-1,
                    location_name="Main Warehouse",
                    inventory_location_name="Main Warehouse",
                    inventory_tracked=True,
                )
            ],
            total_items=1,
            total_inventory_units=18,
        )

        response = get_inventory_table(
            page=1,
            page_size=25,
            sort_order="desc",
            db=object(),
            settings=SimpleNamespace(low_stock_threshold=10),
        )

        get_table.assert_called_once_with(1, 25, "desc")
        self.assertEqual(
            response.model_dump(),
            {
                "items": [
                    {
                        "variant_id": "variant-1",
                        "location_id": "location-1",
                        "product_variant_name": "Classic T-Shirt / Small",
                        "inventory_units": -1,
                        "location": "Main Warehouse",
                        "inventory_tracked": True,
                        "inventory_status": "negative",
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 25,
                    "total_items": 1,
                    "total_pages": 1,
                },
                "totals": {"total_inventory_units": 18},
            },
        )

    def test_route_uses_documented_path_and_schema(self):
        route = next(
            route
            for route in router.routes
            if route.path == "/api/analytics/inventory/table"
        )
        self.assertEqual(route.response_model, InventoryTableResponse)
        self.assertIn("GET", route.methods)

    @patch("app.routers.inventory.InventoryRepository.get_inventory_table")
    def test_endpoint_sanitizes_database_errors(self, get_table):
        get_table.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_inventory_table(
                page=1,
                page_size=25,
                sort_order="asc",
                db=object(),
                settings=SimpleNamespace(low_stock_threshold=10),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve inventory table data.",
        )
        self.assertNotIn("credentials", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
