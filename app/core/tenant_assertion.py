from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError

from app.core.tenant import canonicalize_shop_domain


class TenantAssertionError(ValueError):
    """Raised when frontend-provided tenant context cannot be authenticated."""


@dataclass(frozen=True)
class TenantAssertion:
    shop_domain: str
    assertion_id: str


def verify_tenant_assertion(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
) -> TenantAssertion:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=issuer,
            audience=audience,
            options={
                "require": ["iss", "aud", "sub", "shop", "iat", "nbf", "exp", "jti"]
            },
        )
    except InvalidTokenError as error:
        raise TenantAssertionError("Invalid tenant assertion.") from error

    subject = payload.get("sub")
    shop = payload.get("shop")
    assertion_id = payload.get("jti")
    if not isinstance(subject, str) or not isinstance(shop, str):
        raise TenantAssertionError("Invalid tenant assertion identity.")
    try:
        canonical_shop = canonicalize_shop_domain(shop)
    except ValueError as error:
        raise TenantAssertionError("Invalid tenant assertion shop.") from error
    if subject != canonical_shop:
        raise TenantAssertionError("Tenant assertion subject mismatch.")
    if not isinstance(assertion_id, str) or not assertion_id:
        raise TenantAssertionError("Invalid tenant assertion identifier.")
    return TenantAssertion(canonical_shop, assertion_id)
