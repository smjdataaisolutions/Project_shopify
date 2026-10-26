from dataclasses import dataclass
from urllib.parse import urlparse

import jwt
from jwt import InvalidTokenError

from app.core.tenant import canonicalize_shop_domain


class ShopifyAuthenticationError(ValueError):
    """Raised when a Shopify ID token cannot be authenticated."""


@dataclass(frozen=True)
class ShopifyIdentity:
    shop: str
    user_id: str


def _hostname(value: object, claim_name: str) -> str:
    if not isinstance(value, str):
        raise ShopifyAuthenticationError(f"Missing {claim_name} claim.")

    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ShopifyAuthenticationError(f"Invalid {claim_name} claim.")
    return parsed.hostname.lower()


def verify_shopify_id_token(
    token: str,
    *,
    api_key: str,
    api_secret: str,
) -> ShopifyIdentity:
    """Verify a Shopify ID token and derive its canonical shop identity."""
    try:
        payload = jwt.decode(
            token,
            api_secret,
            algorithms=["HS256"],
            audience=api_key,
            options={
                "require": ["aud", "dest", "exp", "iss", "nbf", "sub"],
            },
        )
    except InvalidTokenError as error:
        raise ShopifyAuthenticationError("Invalid Shopify ID token.") from error

    destination_shop = _hostname(payload.get("dest"), "dest")
    issuer_shop = _hostname(payload.get("iss"), "iss")
    if destination_shop != issuer_shop:
        raise ShopifyAuthenticationError("Shopify token issuer mismatch.")
    try:
        destination_shop = canonicalize_shop_domain(destination_shop)
    except ValueError as error:
        raise ShopifyAuthenticationError("Invalid Shopify shop domain.") from error

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise ShopifyAuthenticationError("Invalid Shopify token subject.")

    return ShopifyIdentity(shop=destination_shop, user_id=user_id)
