from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderLineItem, ProductVariant


@dataclass(frozen=True)
class OverviewSalesMetrics:
    total_revenue: Decimal | None
    total_orders: int
    currency_code: str | None


@dataclass(frozen=True)
class InventoryHealthMetrics:
    products_with_inventory: int
    low_stock_count: int
    out_of_stock_count: int


@dataclass(frozen=True)
class TopProductMetrics:
    product_id: str
    product_title: str | None
    units_sold: int
    product_revenue: Decimal
    currency_code: str | None


class DashboardRepository:
    """PostgreSQL queries used by overview business highlights."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_sales_metrics(self) -> OverviewSalesMetrics:
        """Return sales totals using the same revenue definition as OVR-001."""
        revenue = select(
            func.sum(OrderLineItem.unit_price * OrderLineItem.quantity)
        ).scalar_subquery()
        order_count = select(func.count()).select_from(Order).scalar_subquery()
        line_item_currency = select(
            func.max(OrderLineItem.currency_code)
        ).scalar_subquery()
        order_currency = select(func.max(Order.currency_code)).scalar_subquery()

        row = self.db.execute(
            select(
                revenue.label("total_revenue"),
                order_count.label("total_orders"),
                func.coalesce(line_item_currency, order_currency).label(
                    "currency_code"
                ),
            )
        ).one()
        return OverviewSalesMetrics(
            total_revenue=row.total_revenue,
            total_orders=row.total_orders or 0,
            currency_code=row.currency_code,
        )

    def get_inventory_health(self, low_stock_threshold: int) -> InventoryHealthMetrics:
        """Count products once using store-wide variant inventory quantities."""
        row = self.db.execute(
            select(
                func.count(
                    func.distinct(
                        case(
                            (
                                ProductVariant.inventory_quantity.is_not(None),
                                ProductVariant.product_id,
                            )
                        )
                    )
                ).label("products_with_inventory"),
                func.count(
                    func.distinct(
                        case(
                            (
                                ProductVariant.inventory_quantity.between(
                                    1, low_stock_threshold
                                ),
                                ProductVariant.product_id,
                            )
                        )
                    )
                ).label("low_stock_count"),
                func.count(
                    func.distinct(
                        case(
                            (
                                ProductVariant.inventory_quantity == 0,
                                ProductVariant.product_id,
                            )
                        )
                    )
                ).label("out_of_stock_count"),
            )
        ).one()
        return InventoryHealthMetrics(
            products_with_inventory=row.products_with_inventory or 0,
            low_stock_count=row.low_stock_count or 0,
            out_of_stock_count=row.out_of_stock_count or 0,
        )

    def get_top_selling_product(self) -> TopProductMetrics | None:
        """Return the highest-volume product with deterministic tie-breaking."""
        units_sold = func.sum(OrderLineItem.quantity).label("units_sold")
        product_revenue = func.sum(
            func.coalesce(OrderLineItem.unit_price, 0) * OrderLineItem.quantity
        ).label("product_revenue")
        statement = (
            select(
                OrderLineItem.product_id,
                func.max(OrderLineItem.title).label("product_title"),
                units_sold,
                product_revenue,
                func.max(OrderLineItem.currency_code).label("currency_code"),
            )
            .where(
                OrderLineItem.product_id.is_not(None),
                OrderLineItem.quantity > 0,
            )
            .group_by(OrderLineItem.product_id)
            .order_by(
                units_sold.desc(),
                product_revenue.desc(),
                OrderLineItem.product_id.asc(),
            )
            .limit(1)
        )
        row = self.db.execute(statement).first()
        if row is None:
            return None

        return TopProductMetrics(
            product_id=row.product_id,
            product_title=row.product_title,
            units_sold=row.units_sold,
            product_revenue=row.product_revenue,
            currency_code=row.currency_code,
        )
