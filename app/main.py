from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.shopify_auth import ShopifyAuthenticationError, verify_shopify_id_token
from app.core.tenant import TenantPrincipal
from app.core.tenant_assertion import TenantAssertionError, verify_tenant_assertion
from app.db.session import engine
from app.routers.dashboard import router as dashboard_router
from app.routers.inventory import router as inventory_router
from app.routers.orders import router as orders_router
from app.routers.products import router as products_router
from app.routers.sales import router as sales_router
from app.routers.shopify_webhooks import router as shopify_webhooks_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    engine.dispose()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)
app.include_router(dashboard_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(products_router)
app.include_router(sales_router)
app.include_router(shopify_webhooks_router)


@app.middleware("http")
async def require_shopify_merchant(request: Request, call_next):
    """Require an independently verified Shopify identity for analytics APIs."""
    if not request.url.path.startswith("/api/") or not settings.api_auth_enabled:
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Shopify authentication is required."},
        )

    try:
        identity = verify_shopify_id_token(
            token,
            api_key=settings.shopify_api_key or "",
            api_secret=settings.shopify_api_secret or "",
        )
    except ShopifyAuthenticationError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid Shopify authentication."},
        )

    assertion_token = request.headers.get("x-tenant-assertion", "")
    try:
        assertion = verify_tenant_assertion(
            assertion_token,
            secret=settings.tenant_assertion_secret.get_secret_value()
            if settings.tenant_assertion_secret
            else "",
            issuer=settings.tenant_assertion_issuer,
            audience=settings.tenant_assertion_audience,
        )
    except TenantAssertionError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid tenant authorization."},
        )
    if assertion.shop_domain != identity.shop:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Tenant authorization mismatch."},
        )

    request.state.tenant_principal = TenantPrincipal(
        shop_domain=identity.shop,
        user_id=identity.user_id,
    )
    return await call_next(request)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness_check() -> dict[str, str]:
    """Confirm that the API can establish a database connection."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from error
    return {"status": "ready"}
