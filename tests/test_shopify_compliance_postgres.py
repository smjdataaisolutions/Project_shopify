import os
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.shopify_compliance import apply_shopify_compliance_webhook


@unittest.skipUnless(
    os.environ.get("COMPLIANCE_TEST_DATABASE_URL"),
    "COMPLIANCE_TEST_DATABASE_URL is required for PostgreSQL integration tests.",
)
class ShopifyCompliancePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ["COMPLIANCE_TEST_DATABASE_URL"].replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
        cls.engine = create_engine(database_url)
        with cls.engine.connect() as connection:
            database = connection.execute(text("SELECT current_database()"))
            cls.database_name = database.scalar_one()
        if "_rehearsal_" not in cls.database_name:
            raise RuntimeError(
                "Compliance integration tests require an explicitly named "
                "rehearsal database."
            )

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_data_request_is_idempotent_and_does_not_retain_pii(self):
        with Session(self.engine) as db:
            shop_id = db.execute(
                text(
                    "SELECT id FROM shops "
                    "WHERE shop_domain = 'test-store-martina.myshopify.com'"
                )
            ).scalar_one()
            order_id = db.execute(
                text(
                    "SELECT id FROM orders WHERE shop_id = :shop_id "
                    "ORDER BY id LIMIT 1"
                ),
                {"shop_id": shop_id},
            ).scalar_one()
            payload = {
                "data_request": {"id": "rehearsal-request-001"},
                "customer": {
                    "email": "must-not-persist@example.com",
                    "phone": "+15555550123",
                },
                "orders_requested": [order_id],
            }
            apply_shopify_compliance_webhook(
                db,
                shop_id=shop_id,
                topic="customers/data_request",
                payload=payload,
            )
            apply_shopify_compliance_webhook(
                db,
                shop_id=shop_id,
                topic="customers/data_request",
                payload=payload,
            )
            db.commit()

            count = db.execute(
                text(
                    "SELECT count(1) FROM shopify_compliance_requests "
                    "WHERE shop_id = :shop_id "
                    "AND shopify_request_id = 'rehearsal-request-001'"
                ),
                {"shop_id": shop_id},
            ).scalar_one()
            stored = db.execute(
                text(
                    "SELECT row_to_json(request)::text "
                    "FROM shopify_compliance_requests request "
                    "WHERE shop_id = :shop_id "
                    "AND shopify_request_id = 'rehearsal-request-001'"
                ),
                {"shop_id": shop_id},
            ).scalar_one()

        self.assertEqual(count, 1)
        self.assertNotIn("must-not-persist@example.com", stored)
        self.assertNotIn("+15555550123", stored)


if __name__ == "__main__":
    unittest.main()
