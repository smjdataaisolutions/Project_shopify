from decimal import Decimal
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from the environment (and optionally a local .env file)."""

    database_url: str
    app_name: str = "Shopify Analytics API"
    low_stock_threshold: int = 10
    low_aov_threshold: Decimal = Field(default=Decimal("50.00"), ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
