import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.shopify_webhook import (
    ShopifyWebhookAuthenticationError,
    verify_shopify_webhook_hmac,
)
from app.core.tenant import TenantPrincipal, canonicalize_shop_domain
from app.core.tenant_assertion import TenantAssertionError, verify_tenant_assertion
from app.db.session import get_db
from app.db.tenant_session import register_or_get_tenant
from app.services.shopify_webhook_sync import (
    UnsupportedWebhookTopicError,
    apply_shopify_webhook,
)


router = APIRouter(prefix="/internal", include_in_schema=False)


@router.post("/shopify-webhooks", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_shopify_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_shopify_hmac_sha256: str = Header(default=""),
    x_shopify_shop_domain: str = Header(default=""),
    x_shopify_topic: str = Header(default=""),
    x_tenant_assertion: str = Header(default=""),
) -> Response:
    """Verify and transactionally apply a webhook forwarded by the frontend."""
    settings = get_settings()
    try:
        shop = canonicalize_shop_domain(x_shopify_shop_domain)
        assertion = verify_tenant_assertion(
            x_tenant_assertion,
            secret=settings.tenant_assertion_secret.get_secret_value()
            if settings.tenant_assertion_secret
            else "",
            issuer=settings.tenant_assertion_issuer,
            audience=settings.tenant_assertion_audience,
        )
    except (ValueError, TenantAssertionError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant authorization.",
        ) from error
    if assertion.shop_domain != shop:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant authorization mismatch.",
        )

    body = await request.body()
    try:
        verify_shopify_webhook_hmac(
            body,
            x_shopify_hmac_sha256,
            api_secret=settings.shopify_api_secret or "",
        )
    except ShopifyWebhookAuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Shopify webhook authentication.",
        ) from error

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Shopify webhook payload.",
        ) from error
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Shopify webhook payload.",
        )

    try:
        tenant = register_or_get_tenant(
            TenantPrincipal(shop_domain=shop, user_id="shopify-webhook")
        )
        apply_shopify_webhook(
            db,
            shop_id=tenant.shop_id,
            topic=x_shopify_topic,
            payload=payload,
        )
        db.commit()
    except UnsupportedWebhookTopicError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported Shopify webhook topic.",
        ) from error
    except Exception:
        db.rollback()
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)
