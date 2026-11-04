import unittest
import json

from app.services.shopify_compliance import (
    InvalidCompliancePayloadError,
    UnsupportedComplianceTopicError,
    apply_shopify_compliance_webhook,
)


class FakeSession:
    def __init__(self):
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((str(statement), parameters or {}))


class ShopifyComplianceTests(unittest.TestCase):
    def test_customer_data_request_queues_only_non_pii_identifiers(self):
        db = FakeSession()
        apply_shopify_compliance_webhook(
            db,
            shop_id=17,
            topic="customers/data_request",
            payload={
                "data_request": {"id": 99},
                "customer": {
                    "id": 123,
                    "email": "private@example.com",
                    "phone": "+15555550123",
                },
                "orders_requested": [44, "gid://shopify/Order/45"],
            },
        )
        self.assertEqual(len(db.calls), 1)
        statement, parameters = db.calls[0]
        self.assertIn("ON CONFLICT (shop_id, shopify_request_id)", statement)
        self.assertEqual(parameters["shop_id"], 17)
        self.assertEqual(parameters["shopify_request_id"], "99")
        self.assertEqual(
            set(json.loads(parameters["order_ids"])),
            {"gid://shopify/Order/44", "gid://shopify/Order/45"},
        )
        self.assertNotIn("private@example.com", str(db.calls))
        self.assertNotIn("+15555550123", str(db.calls))

    def test_customer_data_request_requires_request_id(self):
        with self.assertRaises(InvalidCompliancePayloadError):
            apply_shopify_compliance_webhook(
                FakeSession(),
                shop_id=17,
                topic="customers/data_request",
                payload={"orders_requested": [44]},
            )

    def test_customer_redact_deletes_only_requested_tenant_orders(self):
        db = FakeSession()
        apply_shopify_compliance_webhook(
            db,
            shop_id=17,
            topic="customers/redact",
            payload={"orders_to_redact": [44, "gid://shopify/Order/45"]},
        )
        self.assertEqual(len(db.calls), 2)
        self.assertIn("DELETE FROM order_line_items", db.calls[0][0])
        self.assertIn("DELETE FROM orders", db.calls[1][0])
        for _, parameters in db.calls:
            self.assertEqual(parameters["shop_id"], 17)
            self.assertEqual(
                set(parameters["order_ids"]),
                {"gid://shopify/Order/44", "gid://shopify/Order/45"},
            )

    def test_shop_redact_deletes_only_the_authenticated_tenant(self):
        db = FakeSession()
        apply_shopify_compliance_webhook(
            db,
            shop_id=17,
            topic="shop/redact",
            payload={"shop_domain": "redacted.myshopify.com"},
        )
        self.assertEqual(len(db.calls), 9)
        self.assertIn("shopify_compliance_requests", db.calls[0][0])
        self.assertTrue(db.calls[-1][0].startswith("DELETE FROM shops"))
        self.assertTrue(all(parameters == {"shop_id": 17} for _, parameters in db.calls))

    def test_shop_redact_is_idempotent_for_unknown_shop(self):
        db = FakeSession()
        apply_shopify_compliance_webhook(
            db,
            shop_id=None,
            topic="shop/redact",
            payload={},
        )
        self.assertEqual(db.calls, [])

    def test_rejects_non_compliance_topic(self):
        with self.assertRaises(UnsupportedComplianceTopicError):
            apply_shopify_compliance_webhook(
                FakeSession(), shop_id=17, topic="orders/create", payload={}
            )


if __name__ == "__main__":
    unittest.main()
