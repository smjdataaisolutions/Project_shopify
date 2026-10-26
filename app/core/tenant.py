import re
from dataclasses import dataclass


SHOP_DOMAIN_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.myshopify\.com$"
)


class InvalidShopDomainError(ValueError):
    """Raised when a Shopify tenant domain is not canonical and safe."""


def canonicalize_shop_domain(value: str) -> str:
    domain = value.strip().lower().rstrip(".")
    if not SHOP_DOMAIN_PATTERN.fullmatch(domain):
        raise InvalidShopDomainError("Invalid Shopify shop domain.")
    return domain


@dataclass(frozen=True)
class TenantPrincipal:
    shop_domain: str
    user_id: str


@dataclass(frozen=True)
class TenantContext:
    shop_id: int
    shop_domain: str
