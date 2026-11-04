import asyncio
import base64
import hashlib
import hmac
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from pydantic import SecretStr
from starlette.requests import Request

from app.routers.shopify_webhooks import _authenticate_forwarded_webhook


class ShopifyComplianceAuthenticationTests(unittest.TestCase):
    shop = "fashion-store.myshopify.com"
    api_secret = "test-shopify-secret"
    assertion_secret = "0123456789abcdef0123456789abcdef"

    def settings(self):
        return SimpleNamespace(
            shopify_api_secret=self.api_secret,
            tenant_assertion_secret=SecretStr(self.assertion_secret),
            tenant_assertion_issuer="smj-shopify-frontend",
            tenant_assertion_audience="smj-shopify-api",
        )

    def assertion(self, shop=None):
        asserted_shop = shop or self.shop
        now = int(time.time())
        return jwt.encode(
            {
                "iss": "smj-shopify-frontend",
                "aud": "smj-shopify-api",
                "sub": asserted_shop,
                "shop": asserted_shop,
                "iat": now,
                "nbf": now - 1,
                "exp": now + 60,
                "jti": "compliance-assertion-1",
            },
            self.assertion_secret,
            algorithm="HS256",
        )

    def request(self, body):
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "scheme": "https",
                "server": ("private-api.example", 443),
                "path": "/internal/shopify-compliance",
                "raw_path": b"/internal/shopify-compliance",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 12345),
            },
            receive,
        )

    def authenticate(self, payload, *, signature=None, assertion=None, shop=None):
        body = json.dumps(payload, separators=(",", ":")).encode()
        valid_signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        with patch("app.routers.shopify_webhooks.get_settings", self.settings):
            return asyncio.run(
                _authenticate_forwarded_webhook(
                    self.request(body),
                    shop_header=shop or self.shop,
                    hmac_header=signature or valid_signature,
                    tenant_assertion_header=assertion or self.assertion(),
                )
            )

    def test_accepts_matching_hmac_assertion_and_payload_shop(self):
        shop, payload = self.authenticate({"shop_domain": self.shop, "shop_id": 1})
        self.assertEqual(shop, self.shop)
        self.assertEqual(payload["shop_id"], 1)

    def test_rejects_invalid_hmac_with_401(self):
        with self.assertRaises(HTTPException) as context:
            self.authenticate({"shop_domain": self.shop}, signature="invalid")
        self.assertEqual(context.exception.status_code, 401)

    def test_rejects_forged_or_cross_tenant_assertion(self):
        with self.assertRaises(HTTPException) as context:
            self.authenticate(
                {"shop_domain": self.shop},
                assertion=self.assertion("beauty-store.myshopify.com"),
            )
        self.assertEqual(context.exception.status_code, 403)

    def test_rejects_payload_shop_mismatch(self):
        with self.assertRaises(HTTPException) as context:
            self.authenticate({"shop_domain": "beauty-store.myshopify.com"})
        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
