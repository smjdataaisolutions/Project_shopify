from decimal import Decimal

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    """Subset of the existing Shopify products table used by dashboard analytics."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=True
    )
    inventory_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_item_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    inventory_tracked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    product: Mapped[Product | None] = relationship(back_populates="variants")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    currency_code: Mapped[str | None] = mapped_column(String, nullable=True)
    financial_status: Mapped[str | None] = mapped_column(String, nullable=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String, nullable=True)
    subtotal_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_discount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_shipping: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)


class OrderLineItem(Base):
    __tablename__ = "order_line_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str | None] = mapped_column(
        ForeignKey("orders.id"), index=True, nullable=True
    )
    product_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String, nullable=True)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fulfills_online_orders: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_active_inventory: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    address: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class Inventory(Base):
    __tablename__ = "inventory"

    inventory_item_id: Mapped[str] = mapped_column(String, primary_key=True)
    location_id: Mapped[str] = mapped_column(String, primary_key=True)
    location_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    tracked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    requires_shipping: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quantities: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
