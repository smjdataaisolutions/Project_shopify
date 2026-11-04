import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ComplianceMigrationTests(unittest.TestCase):
    def test_up_migration_is_tenant_scoped_and_pii_minimized(self):
        sql = (
            ROOT
            / "migrations"
            / "analytics"
            / "002_shopify_compliance_requests.up.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("FOREIGN KEY (shop_id)", sql)
        self.assertIn("UNIQUE (shop_id, shopify_request_id)", sql)
        self.assertIn("INTERVAL '30 days'", sql)
        self.assertIn("order_ids JSONB", sql)
        for prohibited in ("customer_email", "customer_phone", "raw_payload"):
            self.assertNotIn(prohibited, sql)

    def test_verification_checks_tenant_references_and_json_shape(self):
        sql = (
            ROOT
            / "migrations"
            / "analytics"
            / "002_shopify_compliance_requests.verify.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("invalid_tenant_references", sql)
        self.assertIn("invalid_order_id_documents", sql)


if __name__ == "__main__":
    unittest.main()
