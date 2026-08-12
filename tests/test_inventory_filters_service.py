from datetime import date, datetime, timezone
import unittest

from app.repositories.inventory_repository import (
    InventoryFilterOptions,
    InventoryFilters,
    InventoryLocationOption,
)
from app.services.inventory_service import (
    COLLECTION_UNAVAILABLE_MESSAGE,
    INVENTORY_HISTORY_UNAVAILABLE_MESSAGE,
    InventoryService,
    build_inventory_filters,
)


class StubFilterRepository:
    def get_filter_options(self):
        return InventoryFilterOptions(
            locations=[InventoryLocationOption("location-1", "Main Warehouse")],
            vendors=["Acme"],
            latest_inventory_sync_at=datetime(
                2026, 8, 7, 6, 5, 21, tzinfo=timezone.utc
            ),
        )


class InventoryFilterServiceTests(unittest.TestCase):
    def test_builds_clean_deduplicated_filter_contract(self):
        filters = build_inventory_filters(
            location_ids=[" location-2 ", "location-1", "location-1"],
            vendors=[" Acme ", "Acme"],
            inventory_tracked=True,
            inventory_statuses=["out_of_stock", "low_stock"],
        )

        self.assertEqual(
            filters,
            InventoryFilters(
                location_ids=("location-1", "location-2"),
                vendors=("Acme",),
                inventory_tracked=True,
                inventory_statuses=("low_stock", "out_of_stock"),
            ),
        )

    def test_rejects_date_collection_and_unknown_status_filters(self):
        with self.assertRaisesRegex(ValueError, INVENTORY_HISTORY_UNAVAILABLE_MESSAGE):
            build_inventory_filters(start_date=date(2026, 8, 1))
        with self.assertRaisesRegex(ValueError, COLLECTION_UNAVAILABLE_MESSAGE):
            build_inventory_filters(collection_ids=["collection-1"])
        with self.assertRaisesRegex(ValueError, "Unsupported inventory status: bad"):
            build_inventory_filters(inventory_statuses=["bad"])

    def test_returns_dynamic_and_capability_filter_options(self):
        response = InventoryService(StubFilterRepository(), 10).get_filter_options()
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["locations"], [{"id": "location-1", "name": "Main Warehouse"}])
        self.assertEqual(payload["vendors"], ["Acme"])
        self.assertFalse(payload["collections"]["supported"])
        self.assertEqual(payload["collections"]["options"], [])
        self.assertFalse(payload["date_range"]["supported"])
        self.assertEqual(payload["date_range"]["message"], INVENTORY_HISTORY_UNAVAILABLE_MESSAGE)
        self.assertEqual(
            {item["value"] for item in payload["inventory_statuses"]},
            {"healthy", "low_stock", "out_of_stock", "negative", "untracked", "unknown"},
        )
        self.assertEqual(
            [item["value"] for item in payload["inventory_tracked"]],
            [True, False],
        )


if __name__ == "__main__":
    unittest.main()
