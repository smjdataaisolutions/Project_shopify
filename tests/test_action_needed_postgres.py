import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.dashboard_repository import DashboardRepository
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

if __name__ == "__main__":
    unittest.main()
