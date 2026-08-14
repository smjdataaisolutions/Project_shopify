from datetime import date
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.sales_repository import SalesFilters, SalesRepository
from app.schemas.sales import (
    DailySalesBreakdownResponse,
    RevenueTrendResponse,
    SalesActionNeededResponse,
    SalesFilterOptionsResponse,
    SalesSummary,
)
from app.services.sales_service import SalesService, build_sales_filters


router = APIRouter(prefix="/api/sales", tags=["sales"])
logger = logging.getLogger(__name__)


def get_sales_filters(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    sales_channel: Annotated[list[str] | None, Query()] = None,
    financial_status: Annotated[list[str] | None, Query()] = None,
    currency: Annotated[list[str] | None, Query()] = None,
) -> SalesFilters:
    try:
        return build_sales_filters(
            start_date,
            end_date,
            sales_channel,
            financial_status,
            currency,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/summary", response_model=SalesSummary)
def get_sales_summary(
    filters: SalesFilters = Depends(get_sales_filters),
    db: Session = Depends(get_db),
) -> SalesSummary:
    """Return aggregate sales metrics with one PostgreSQL table scan."""
    try:
        return SalesService(SalesRepository(db)).get_sales_summary(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve the sales summary")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve sales summary data."
        ) from error


@router.get("/daily-breakdown", response_model=DailySalesBreakdownResponse)
def get_daily_sales_breakdown(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: Literal[
        "date",
        "gross_sales",
        "discounts",
        "returns_refunds",
        "net_sales",
        "shipping",
        "tax",
        "total_sales",
        "orders",
        "average_order_value",
    ] = Query(default="date"),
    sort_direction: Literal["asc", "desc"] = Query(default="desc"),
    filters: SalesFilters = Depends(get_sales_filters),
    db: Session = Depends(get_db),
) -> DailySalesBreakdownResponse:
    """Return filtered daily Sales KPI metrics with complete-result totals."""
    try:
        return SalesService(SalesRepository(db)).get_daily_breakdown(
            filters, page, page_size, sort_by, sort_direction
        )
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve the daily sales breakdown")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve daily sales breakdown."
        ) from error


@router.get("/filter-options", response_model=SalesFilterOptionsResponse)
def get_sales_filter_options(
    db: Session = Depends(get_db),
) -> SalesFilterOptionsResponse:
    """Return PostgreSQL-backed dimensions for the Sales filter panel."""
    try:
        return SalesService(SalesRepository(db)).get_filter_options()
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve the sales filter options")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve sales filter options."
        ) from error


@router.get("/revenue/trend", response_model=RevenueTrendResponse)
def get_revenue_trend(
    interval: Literal["daily"] = Query(default="daily"),
    filters: SalesFilters = Depends(get_sales_filters),
    db: Session = Depends(get_db),
) -> RevenueTrendResponse:
    """Return order revenue grouped by processed date for chart rendering."""
    service = SalesService(SalesRepository(db))
    try:
        return service.get_revenue_trend(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve the revenue trend")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve revenue trend data."
        ) from error


@router.get("/action-needed", response_model=SalesActionNeededResponse)
def get_sales_action_needed(
    filters: SalesFilters = Depends(get_sales_filters),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SalesActionNeededResponse:
    """Return deterministic sales recommendations for the selected period."""
    service = SalesService(
        SalesRepository(db),
        settings.low_aov_threshold,
        settings.high_discount_rate_threshold,
        settings.refund_rate_threshold,
        settings.cancellation_rate_threshold,
    )
    try:
        return service.get_action_needed(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve sales action needed recommendations")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve sales action needed recommendations.",
        ) from error


@router.get("/action-needed/{action_id}/download")
def download_sales_action_needed_records(
    action_id: str,
    filters: SalesFilters = Depends(get_sales_filters),
    db: Session = Depends(get_db),
) -> Response:
    """Download the PostgreSQL records contributing to a supported action."""
    try:
        export = SalesService(SalesRepository(db)).get_action_export(
            action_id, filters
        )
        return Response(
            content=export.content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{export.filename}"'
            },
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Unable to export sales action needed records")
        raise HTTPException(
            status_code=500,
            detail="Unable to export sales action needed records.",
        ) from error
