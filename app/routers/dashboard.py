from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Order, OrderLineItem, Product, ProductVariant
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary


router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardSummary:
    """Return product and inventory summary values for the Shopify dashboard."""
    threshold = get_settings().low_stock_threshold

    total_products = db.scalar(select(func.count()).select_from(Product)) or 0
    total_variants = db.scalar(select(func.count()).select_from(ProductVariant)) or 0

    # Each metric is a count of products, even if a product has several matching variants.
    low_stock_products = db.scalar(
        select(func.count(func.distinct(ProductVariant.product_id))).where(
            ProductVariant.inventory_quantity < threshold,
        )
    ) or 0
    out_of_stock_products = db.scalar(
        select(func.count(func.distinct(ProductVariant.product_id))).where(
            ProductVariant.inventory_quantity == 0,
        )
    ) or 0

    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    total_revenue = db.scalar(
        select(func.coalesce(func.sum(OrderLineItem.unit_price * OrderLineItem.quantity), 0))
    ) or 0
    units_sold = db.scalar(
        select(func.coalesce(func.sum(OrderLineItem.quantity), 0))
    ) or 0
    average_order_value = total_revenue / total_orders if total_orders else 0

    return DashboardSummary(
        total_products=total_products,
        total_variants=total_variants,
        low_stock_products=low_stock_products,
        out_of_stock_products=out_of_stock_products,
        total_orders=total_orders,
        total_revenue=float(total_revenue),
        units_sold=units_sold,
        average_order_value=float(average_order_value),
    )
