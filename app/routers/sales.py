from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.sales import SalesSummary


router = APIRouter(prefix="/api/sales", tags=["sales"])


SALES_SUMMARY_SQL = text("""
    SELECT
        COALESCE(SUM(subtotal_price), 0) AS gross_sales,
        COALESCE(SUM(total_discount), 0) AS discounts,
        COALESCE(SUM(COALESCE(subtotal_price, 0) - COALESCE(total_discount, 0)), 0)
            AS net_sales,
        COALESCE(SUM(total_shipping), 0) AS shipping,
        COALESCE(SUM(total_tax), 0) AS taxes,
        COALESCE(SUM(total_price), 0) AS total_sales,
        COUNT(*) AS orders_count,
        COALESCE(SUM(total_price) / NULLIF(COUNT(*), 0), 0) AS average_order_value
    FROM orders
""")


@router.get("/summary", response_model=SalesSummary)
def get_sales_summary(
    db: Session = Depends(get_db),
) -> SalesSummary:
    """Return aggregate sales metrics with one PostgreSQL table scan."""
    summary = db.execute(SALES_SUMMARY_SQL).mappings().one()
    return SalesSummary(
        gross_sales=float(summary["gross_sales"]),
        discounts=float(summary["discounts"]),
        net_sales=float(summary["net_sales"]),
        shipping=float(summary["shipping"]),
        taxes=float(summary["taxes"]),
        total_sales=float(summary["total_sales"]),
        orders_count=summary["orders_count"],
        average_order_value=float(summary["average_order_value"]),
    )
