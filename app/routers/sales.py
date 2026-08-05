from datetime import date
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.sales_repository import SalesRepository
from app.schemas.sales import RevenueTrendResponse, SalesSummary
from app.services.sales_service import SalesService


router = APIRouter(prefix="/api/sales", tags=["sales"])
logger = logging.getLogger(__name__)


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


@router.get("/revenue/trend", response_model=RevenueTrendResponse)
def get_revenue_trend(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    interval: Literal["daily"] = Query(default="daily"),
    db: Session = Depends(get_db),
) -> RevenueTrendResponse:
    """Return order revenue grouped by processed date for chart rendering."""
    service = SalesService(SalesRepository(db))
    try:
        return service.get_revenue_trend(start_date, end_date)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve the revenue trend")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve revenue trend data."
        ) from error
