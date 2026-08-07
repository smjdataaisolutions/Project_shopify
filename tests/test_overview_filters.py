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
        )

        self.assertEqual(filters.financial_statuses, ("PAID", "REFUNDED"))
        self.assertEqual(filters.fulfillment_statuses, ("FULFILLED",))

    def test_rejects_reversed_date_range(self):
        with self.assertRaisesRegex(
            ValueError, "start_date must be on or before end_date"
        ):
            build_overview_filters(
                date(2026, 8, 6),
                date(2026, 8, 1),
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
