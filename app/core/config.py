from decimal import Decimal
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from the environment (and optionally a local .env file)."""

    database_url: str
    app_name: str = "Shopify Analytics API"
    deployment_environment: str = "development"
    api_docs_enabled: bool = True
    api_auth_enabled: bool = False
    shopify_api_key: str | None = None
    shopify_api_secret: str | None = None
    tenant_assertion_secret: SecretStr | None = None
    tenant_assertion_issuer: str = "smj-shopify-frontend"
    tenant_assertion_audience: str = "smj-shopify-api"
    database_pool_size: int = Field(default=2, ge=1, le=20)
    database_max_overflow: int = Field(default=2, ge=0, le=20)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=120)
    database_pool_recycle_seconds: int = Field(default=300, ge=30, le=3600)
    low_stock_threshold: int = 10
    low_aov_threshold: Decimal = Field(default=Decimal("50.00"), ge=0)
    high_discount_rate_threshold: Decimal = Field(
        default=Decimal("0.20"), ge=0, le=1
    )
    refund_rate_threshold: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    cancellation_rate_threshold: Decimal = Field(
        default=Decimal("0.10"), ge=0, le=1
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_staging_authentication(self) -> "Settings":
        environment = self.deployment_environment.strip().lower()
        if environment in {"staging", "production"} and not self.api_auth_enabled:
            raise ValueError(
                "API_AUTH_ENABLED must be true in staging and production."
            )

        if self.api_auth_enabled:
            def is_missing(value: object) -> bool:
                if isinstance(value, SecretStr):
                    return not value.get_secret_value().strip()
                return not isinstance(value, str) or not value.strip()

            missing = [
                name
                for name, value in (
                    ("SHOPIFY_API_KEY", self.shopify_api_key),
                    ("SHOPIFY_API_SECRET", self.shopify_api_secret),
                    ("TENANT_ASSERTION_SECRET", self.tenant_assertion_secret),
                )
                if is_missing(value)
            ]
            if missing:
                raise ValueError(
                    "Missing API authentication settings: " + ", ".join(missing)
                )

            assertion_secret = self.tenant_assertion_secret
            if assertion_secret and len(assertion_secret.get_secret_value()) < 32:
                raise ValueError(
                    "TENANT_ASSERTION_SECRET must contain at least 32 characters."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
