import time
import unittest
from unittest.mock import patch

import jwt
from pydantic import ValidationError

from app.core.config import Settings
from app.core.shopify_auth import (
    ShopifyAuthenticationError,
    verify_shopify_id_token,
)
from app.core.tenant_assertion import TenantAssertionError, verify_tenant_assertion


class ShopifyIdTokenTests(unittest.TestCase):
    api_key = "test-api-key"
    api_secret = "test-api-secret"
    shop = "test-store-martina.myshopify.com"

    def make_token(self, **overrides):
        now = int(time.time())
        payload = {
            "aud": self.api_key,
            "dest": f"https://{self.shop}",
            "exp": now + 60,
            "iss": f"https://{self.shop}/admin",
            "nbf": now - 1,
            "sub": "12345",
        }
        payload.update(overrides)
        return jwt.encode(payload, self.api_secret, algorithm="HS256")

    def verify(self, token):
        return verify_shopify_id_token(
            token,
            api_key=self.api_key,
            api_secret=self.api_secret,
        )

    def test_accepts_valid_token_for_permitted_shop(self):
        identity = self.verify(self.make_token())
        self.assertEqual(identity.shop, self.shop)
        self.assertEqual(identity.user_id, "12345")

    def test_rejects_wrong_audience(self):
        with self.assertRaises(ShopifyAuthenticationError):
            self.verify(self.make_token(aud="another-app"))

    def test_rejects_mismatched_issuer_and_destination(self):
        with self.assertRaises(ShopifyAuthenticationError):
            self.verify(
                self.make_token(iss="https://another-shop.myshopify.com/admin")
            )

    def test_accepts_another_valid_shopify_shop(self):
        token = self.make_token(
            dest="https://another-shop.myshopify.com",
            iss="https://another-shop.myshopify.com/admin",
        )
        self.assertEqual(self.verify(token).shop, "another-shop.myshopify.com")

    def test_rejects_expired_token(self):
        with self.assertRaises(ShopifyAuthenticationError):
            self.verify(self.make_token(exp=int(time.time()) - 1))


class TenantAssertionTests(unittest.TestCase):
    secret = "0123456789abcdef0123456789abcdef"

    def make_assertion(self, **overrides):
        now = int(time.time())
        payload = {
            "iss": "smj-shopify-frontend",
            "aud": "smj-shopify-api",
            "sub": "fashion-store.myshopify.com",
            "shop": "fashion-store.myshopify.com",
            "iat": now,
            "nbf": now - 1,
            "exp": now + 60,
            "jti": "assertion-1",
        }
        payload.update(overrides)
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def verify(self, token):
        return verify_tenant_assertion(
            token,
            secret=self.secret,
            issuer="smj-shopify-frontend",
            audience="smj-shopify-api",
        )

    def test_accepts_valid_short_lived_assertion(self):
        self.assertEqual(
            self.verify(self.make_assertion()).shop_domain,
            "fashion-store.myshopify.com",
        )

    def test_rejects_forged_expired_and_mismatched_assertions(self):
        with self.assertRaises(TenantAssertionError):
            verify_tenant_assertion(
                self.make_assertion(),
                secret="abcdef0123456789abcdef0123456789",
                issuer="smj-shopify-frontend",
                audience="smj-shopify-api",
            )
        with self.assertRaises(TenantAssertionError):
            self.verify(self.make_assertion(exp=int(time.time()) - 1))
        with self.assertRaises(TenantAssertionError):
            self.verify(self.make_assertion(sub="beauty-store.myshopify.com"))


class StagingAuthenticationConfigurationTests(unittest.TestCase):
    def test_staging_fails_closed_when_api_authentication_is_disabled(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(
                    database_url="postgresql://test:test@localhost/test",
                    deployment_environment="staging",
                )

    def test_staging_accepts_complete_multi_tenant_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(
                database_url="postgresql://test:test@localhost/test",
                deployment_environment="staging",
                api_auth_enabled=True,
                shopify_api_key="key",
                shopify_api_secret="secret",
                tenant_assertion_secret="0123456789abcdef0123456789abcdef",
            )
        self.assertEqual(settings.tenant_assertion_audience, "smj-shopify-api")


if __name__ == "__main__":
    unittest.main()
