import base64
import hashlib
import hmac


class ShopifyWebhookAuthenticationError(ValueError):
    """Raised when a Shopify webhook signature cannot be authenticated."""


def verify_shopify_webhook_hmac(
    body: bytes,
    encoded_hmac: str,
    *,
    api_secret: str,
) -> None:
    """Verify Shopify's base64-encoded HMAC-SHA256 signature."""
    if not body or not encoded_hmac or not api_secret:
        raise ShopifyWebhookAuthenticationError("Missing webhook authentication data.")

    digest = hmac.new(
        api_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("ascii")
    if not hmac.compare_digest(expected, encoded_hmac.strip()):
        raise ShopifyWebhookAuthenticationError("Invalid Shopify webhook signature.")
