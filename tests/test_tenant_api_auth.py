import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from pydantic import SecretStr
from starlette.requests import Request
from starlette.responses import Response

from app.main import require_shopify_merchant


class TenantApiAuthenticationTests(unittest.TestCase):
    api_key = "test-api-key"
    api_secret = "test-shopify-secret"
    assertion_secret = "0123456789abcdef0123456789abcdef"

    def settings(self):
        return SimpleNamespace(
            api_auth_enabled=True,
            shopify_api_key=self.api_key,
            shopify_api_secret=self.api_secret,
            tenant_assertion_secret=SecretStr(self.assertion_secret),
            tenant_assertion_issuer="smj-shopify-frontend",
            tenant_assertion_audience="smj-shopify-api",
        )

    def shopify_token(self, shop):
        now = int(time.time())
        return jwt.encode(
            {
                "aud": self.api_key,
                "dest": f"https://{shop}",
                "iss": f"https://{shop}/admin",
                "sub": "user-1",
                "iat": now,
                "nbf": now - 1,
                "exp": now + 60,
            },
            self.api_secret,
            algorithm="HS256",
        )

    def assertion(self, shop):
        now = int(time.time())
        return jwt.encode(
            {
                "iss": "smj-shopify-frontend",
                "aud": "smj-shopify-api",
                "sub": shop,
                "shop": shop,
                "iat": now,
                "nbf": now - 1,
                "exp": now + 60,
                "jti": "assertion-1",
            },
            self.assertion_secret,
            algorithm="HS256",
        )

    def request(self, headers=None):
        encoded_headers = [
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in (headers or {}).items()
        ]
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "scheme": "https",
                "server": ("api.example", 443),
                "path": "/api/dashboard",
                "raw_path": b"/api/dashboard",
                "query_string": b"",
                "headers": encoded_headers,
                "client": ("127.0.0.1", 12345),
            }
        )

        async def next_handler(_request):
            return Response(status_code=204)

        with patch("app.main.settings", self.settings()):
            return asyncio.run(require_shopify_merchant(request, next_handler))

    def test_unauthenticated_and_missing_assertion_requests_are_rejected(self):
        self.assertEqual(self.request().status_code, 401)
        token = self.shopify_token("fashion-store.myshopify.com")
        response = self.request({"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_shopify_identity_cannot_select_another_asserted_tenant(self):
        token = self.shopify_token("fashion-store.myshopify.com")
        assertion = self.assertion("beauty-store.myshopify.com")
        response = self.request(
            {
                "Authorization": f"Bearer {token}",
                "X-Tenant-Assertion": assertion,
            }
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
