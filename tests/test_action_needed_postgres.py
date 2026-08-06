import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.dashboard_repository import DashboardRepository, OverviewFilters
from app.services.dashboard_service import ActionNeededService


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class ActionNeededPostgresTests(unittest.TestCase):
    def test_reads_real_aggregates_and_builds_valid_response(self):
        settings = get_settings()
        with SessionLocal() as db:
            response = ActionNeededService(
                DashboardRepository(db),
                settings.low_aov_threshold,
            ).get_actions()

        payload = response.model_dump(mode="json")
        self.assertIn("actions", payload)
        self.assertLessEqual(len(payload["actions"]), 5)

    def test_location_filter_reads_synchronized_inventory(self):
        settings = get_settings()
        with SessionLocal() as db:
            repository = DashboardRepository(db)
            options = repository.get_filter_options()
            if not options.locations:
                self.skipTest("No synchronized locations are available.")
            response = ActionNeededService(
                repository,
                settings.low_aov_threshold,
                settings.low_stock_threshold,
            ).get_actions(
                OverviewFilters(location_ids=(options.locations[0].id,))
            )

        self.assertLessEqual(len(response.actions), 5)


if __name__ == "__main__":
    unittest.main()
