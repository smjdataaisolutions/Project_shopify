import base64
import hashlib
import hmac
import unittest

from app.core.shopify_webhook import (
    ShopifyWebhookAuthenticationError,
    verify_shopify_webhook_hmac,
)
from app.services.shopify_webhook_sync import (
    UnsupportedWebhookTopicError,
    apply_shopify_webhook,
)


class FakeResult:
    def __init__(self, *, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self


class FakeSession:
    def __init__(self):
        self.calls = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.calls.append((sql, parameters or {}))
        return FakeResult()

    @property
    def sql(self):
        return "\n".join(value[0] for value in self.calls)


class ShopifyWebhookHmacTests(unittest.TestCase):
    def test_accepts_valid_hmac_and_rejects_modified_body(self):
        body = b'{"id":123}'
        secret = "shpss_test"
        signature = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()

        verify_shopify_webhook_hmac(body, signature, api_secret=secret)
        with self.assertRaises(ShopifyWebhookAuthenticationError):
            verify_shopify_webhook_hmac(
                b'{"id":124}', signature, api_secret=secret
            )


class ShopifyWebhookSynchronizationTests(unittest.TestCase):
    def test_product_event_updates_products_variants_and_sync_state(self):
        db = FakeSession()
        apply_shopify_webhook(
            db,
            shop_id=101,
            topic="products/update",
            payload={
                "id": 1,
                "title": "Board",
                "tags": "winter, snow",
                "variants": [
                    {
                        "id": 2,
                        "title": "Default",
                        "inventory_item_id": 3,
                        "inventory_management": "shopify",
                    }
                ],
            },
        )
        self.assertIn("INSERT INTO products", db.sql)
        self.assertIn("INSERT INTO product_variants", db.sql)
        self.assertIn("INSERT INTO shopify_sync_state", db.sql)
        parameters = [params for _, params in db.calls]
        self.assertTrue(all(p.get("shop_id") == 101 for p in parameters if p))
        self.assertIn("gid://shopify/Product/1", [p.get("id") for p in parameters])
        self.assertIn(
            "gid://shopify/ProductVariant/2", [p.get("id") for p in parameters]
        )

    def test_inventory_level_event_uses_inventory_and_location_gids(self):
        db = FakeSession()
        apply_shopify_webhook(
            db,
            shop_id=101,
            topic="inventory_levels/update",
            payload={
                "inventory_item_id": 11,
                "location_id": 22,
                "available": 7,
                "admin_graphql_api_id": "gid://shopify/InventoryLevel/ignored",
            },
        )
        self.assertIn("INSERT INTO inventory", db.sql)
        inventory_call = next(
            params for sql, params in db.calls if "INSERT INTO inventory" in sql
        )
        self.assertEqual(inventory_call["item_id"], "gid://shopify/InventoryItem/11")
        self.assertEqual(inventory_call["location_id"], "gid://shopify/Location/22")

    def test_location_event_updates_location_and_inventory_names(self):
        db = FakeSession()
        apply_shopify_webhook(
            db,
            shop_id=101,
            topic="locations/update",
            payload={"id": 7, "name": "Main", "active": True},
        )
        self.assertIn("INSERT INTO locations", db.sql)
        self.assertIn("UPDATE inventory SET location_name", db.sql)

    def test_order_event_updates_order_and_line_items(self):
        db = FakeSession()
        apply_shopify_webhook(
            db,
            shop_id=101,
            topic="orders/create",
            payload={
                "id": 9,
                "name": "#1009",
                "currency": "USD",
                "total_price": "25.00",
                "line_items": [
                    {
                        "id": 10,
                        "product_id": 1,
                        "variant_id": 2,
                        "title": "Board",
                        "quantity": 1,
                        "price": "25.00",
                    }
                ],
            },
        )
        self.assertIn("INSERT INTO orders", db.sql)
        self.assertIn("INSERT INTO order_line_items", db.sql)
        parameters = [params for _, params in db.calls]
        self.assertIn("gid://shopify/Order/9", [p.get("id") for p in parameters])
        self.assertIn("gid://shopify/LineItem/10", [p.get("id") for p in parameters])

    def test_rejects_unconfigured_topic(self):
        with self.assertRaises(UnsupportedWebhookTopicError):
            apply_shopify_webhook(
                FakeSession(), shop_id=101, topic="customers/create", payload={}
            )

    def test_uninstall_marks_only_the_authenticated_tenant(self):
        db = FakeSession()
        apply_shopify_webhook(
            db,
            shop_id=101,
            topic="app/uninstalled",
            payload={"shop_domain": "example.myshopify.com"},
        )
        self.assertIn("UPDATE shops", db.sql)
        self.assertEqual(db.calls[-1][1], {"shop_id": 101})
        self.assertNotIn("DELETE FROM orders", db.sql)


if __name__ == "__main__":
    unittest.main()
