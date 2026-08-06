from datetime import date
import unittest

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import Order
from app.repositories.dashboard_repository import DashboardRepository, OverviewFilters
from app.routers.dashboard import router
from app.schemas.dashboard import OverviewFilterOptionsResponse
from app.services.dashboard_service import build_overview_filters


class OverviewFilterTests(unittest.TestCase):
    def test_builds_deduplicated_filter_criteria(self):
        filters = build_overview_filters(
            date(2026, 8, 1),
            date(2026, 8, 6),
            ["PAID", "PAID", "REFUNDED"],
            ["FULFILLED"],
            "low_stock",
            ["location-1", "location-1"],
        )

        self.assertEqual(filters.financial_statuses, ("PAID", "REFUNDED"))
        self.assertEqual(filters.fulfillment_statuses, ("FULFILLED",))
        self.assertEqual(filters.inventory_status, "low_stock")
        self.assertEqual(filters.location_ids, ("location-1",))

    def test_rejects_reversed_date_range(self):
        with self.assertRaisesRegex(
            ValueError, "start_date must be on or before end_date"
        ):
            build_overview_filters(
                date(2026, 8, 6),
                date(2026, 8, 1),
                None,
                None,
                None,
                None,
            )

    def test_order_filters_use_processed_at_and_exact_stored_values(self):
        repository = DashboardRepository(db=object())
        statement = repository._apply_order_filters(
            select(Order.id),
            OverviewFilters(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 6),
                financial_statuses=("PAID",),
                fulfillment_statuses=("FULFILLED",),
            ),
        )
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("orders.processed_at >= '2026-08-01'", sql)
        self.assertIn("orders.processed_at < '2026-08-07'", sql)
        self.assertIn("orders.financial_status IN ('PAID')", sql)
        self.assertIn("orders.fulfillment_status IN ('FULFILLED')", sql)

    def test_location_inventory_uses_available_quantity_and_shared_threshold(self):
        repository = DashboardRepository(db=object())
        statement = repository._filtered_inventory_rows(
            OverviewFilters(
                inventory_status="low_stock",
                location_ids=("location-1",),
            ),
            low_stock_threshold=10,
        )
        sql = str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("jsonb_path_query_first", sql)
        self.assertIn("inventory.location_id IN ('location-1')", sql)
        self.assertIn("BETWEEN 1 AND 10", sql)

    def test_filter_options_route_uses_documented_path_and_response_model(self):
        route = next(
            route
            for route in router.routes
            if route.path == "/api/analytics/overview/filter-options"
        )

        self.assertEqual(route.response_model, OverviewFilterOptionsResponse)
        self.assertIn("GET", route.methods)


if __name__ == "__main__":
    unittest.main()
