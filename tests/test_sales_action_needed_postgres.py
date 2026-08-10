import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.sales_repository import SalesFilters
from app.repositories.sales_repository import SalesRepository
from app.services.sales_service import SalesService


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class SalesActionNeededPostgresTests(unittest.TestCase):
    def test_reads_real_sales_aggregates_and_builds_valid_response(self):
        settings = get_settings()
        with SessionLocal() as db:
            service = SalesService(
                SalesRepository(db),
                settings.low_aov_threshold,
                settings.high_discount_rate_threshold,
                settings.refund_rate_threshold,
                settings.cancellation_rate_threshold,
            )
            response = service.get_action_needed(SalesFilters())
            export = service.get_action_export(
                "sales_refund_cancellation_spike", SalesFilters()
            )

        payload = response.model_dump(mode="json")
        self.assertIn("has_sufficient_data", payload)
        self.assertIn("actions", payload)
        self.assertLessEqual(len(payload["actions"]), 5)
        self.assertTrue(export.content.startswith(
            "order_id,product_name,financial_status,amount_refunded,"
            "refund_reason,cancelled_at,refunded_date"
        ))

if __name__ == "__main__":
    unittest.main()
