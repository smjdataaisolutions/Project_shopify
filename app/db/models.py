from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
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
    inventory_tracked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    product: Mapped[Product | None] = relationship(back_populates="variants")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)


class OrderLineItem(Base):
    __tablename__ = "order_line_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str | None] = mapped_column(
        ForeignKey("orders.id"), index=True, nullable=True
    )
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
