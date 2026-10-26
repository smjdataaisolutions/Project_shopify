from decimal import Decimal

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Shop(Base):
    """Stable tenant identity; Shopify credentials remain in session storage."""

    __tablename__ = "shops"
    __table_args__ = (
        UniqueConstraint("shop_domain", name="uq_shops_shop_domain"),
        CheckConstraint(
            "shop_domain = lower(shop_domain) "
            "AND shop_domain ~ '^[a-z0-9][a-z0-9-]*[a-z0-9]\\.myshopify\\.com$'",
            name="ck_shops_canonical_domain",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'uninstalled')",
            name="ck_shops_status",
        ),
        CheckConstraint(
            "sync_status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_shops_sync_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )
    shop_domain: Mapped[str] = mapped_column(String, nullable=False)
    shopify_shop_gid: Mapped[str | None] = mapped_column(String, nullable=True)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    uninstalled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="active"
    )
    sync_status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending"
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TenantOwned:
    """Marker used by the tenant-scoped SQLAlchemy session."""

    shop_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shops.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class Product(TenantOwned, Base):
    """Subset of the existing Shopify products table used by dashboard analytics."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor: Mapped[str | None] = mapped_column(String, nullable=True)
    product_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product")


class ProductVariant(TenantOwned, Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shop_id", "product_id"],
            ["products.shop_id", "products.id"],
            name="fk_product_variants_shop_product",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    inventory_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_item_id: Mapped[str | None] = mapped_column(
        String, index=True, nullable=True
    )
    inventory_tracked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    product: Mapped[Product | None] = relationship(back_populates="variants")


class Location(TenantOwned, Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)


class InventoryLevel(TenantOwned, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shop_id", "location_id"],
            ["locations.shop_id", "locations.id"],
            name="fk_inventory_shop_location",
            ondelete="RESTRICT",
        ),
    )

    inventory_item_id: Mapped[str] = mapped_column(String, primary_key=True)
    location_id: Mapped[str] = mapped_column(String, primary_key=True)
    location_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tracked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quantities: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Order(TenantOwned, Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    currency_code: Mapped[str | None] = mapped_column(String, nullable=True)
    financial_status: Mapped[str | None] = mapped_column(String, nullable=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String, nullable=True)
    sales_channel: Mapped[str | None] = mapped_column(String, nullable=True)
    subtotal_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_discount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_shipping: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_refunded: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class OrderLineItem(TenantOwned, Base):
    __tablename__ = "order_line_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shop_id", "order_id"],
            ["orders.shop_id", "orders.id"],
            name="fk_order_line_items_shop_order",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    product_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String, nullable=True)


class ShopifySyncState(TenantOwned, Base):
    __tablename__ = "shopify_sync_state"

    source: Mapped[str] = mapped_column(String, primary_key=True)
    last_successful_sync_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
