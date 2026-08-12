from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.inventory_repository import InventoryFilters
from app.routers.inventory import get_inventory_filter_options, get_inventory_filters, router
from app.schemas.inventory import InventoryFilterOptionsResponse
from app.services.inventory_service import INVENTORY_HISTORY_UNAVAILABLE_MESSAGE


class InventoryFilterApiTests(unittest.TestCase):
    def test_dependency_maps_repeated_query_values(self):
        filters = get_inventory_filters(
            start_date=None,
            end_date=None,
            location_id=["location-1", "location-2"],
            vendor=["Acme"],
            collection_id=None,
            inventory_tracked=False,
            inventory_status=["negative", "out_of_stock"],
        )

        self.assertEqual(
            filters,
            InventoryFilters(
                location_ids=("location-1", "location-2"),
                vendors=("Acme",),
                inventory_tracked=False,
                inventory_statuses=("negative", "out_of_stock"),
            ),
        )

    def test_dependency_returns_422_for_unavailable_history(self):
        with self.assertRaises(HTTPException) as context:
            get_inventory_filters(
                start_date=date(2026, 8, 1),
                end_date=None,
                location_id=None,
                vendor=None,
                collection_id=None,
                inventory_tracked=None,
                inventory_status=None,
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(context.exception.detail, INVENTORY_HISTORY_UNAVAILABLE_MESSAGE)

    def test_route_is_the_single_new_typed_endpoint(self):
        route = next(
            route
            for route in router.routes
            if route.path == "/api/analytics/inventory/filter-options"
        )
        self.assertEqual(route.response_model, InventoryFilterOptionsResponse)
        self.assertIn("GET", route.methods)

    @patch("app.routers.inventory.InventoryRepository.get_filter_options")
    def test_filter_options_endpoint_sanitizes_database_errors(self, get_options):
        get_options.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_inventory_filter_options(
                db=object(),
                settings=SimpleNamespace(low_stock_threshold=10),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve inventory filter options.",
        )


if __name__ == "__main__":
    unittest.main()
