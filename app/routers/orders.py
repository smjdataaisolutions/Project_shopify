from datetime import date
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.orders_repository import OrderFilters, OrdersRepository
from app.schemas.orders import (
    OrderChartsResponse,
    OrderKpiResponse,
    OrderPerformanceResponse,
    OrderTimelineResponse,
)
from app.services.orders_service import OrdersService, build_order_filters


router = APIRouter(prefix="/api/orders", tags=["orders"])
logger = logging.getLogger(__name__)


def get_order_filters(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    sales_channel: Annotated[list[str] | None, Query()] = None,
    order_status: Annotated[list[str] | None, Query()] = None,
    fulfillment_status: Annotated[list[str] | None, Query()] = None,
    payment_status: Annotated[list[str] | None, Query()] = None,
) -> OrderFilters:
    try:
        return build_order_filters(
            start_date,
            end_date,
            sales_channel,
            order_status,
            fulfillment_status,
            payment_status,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/kpis", response_model=OrderKpiResponse)
def get_order_kpis(
    filters: OrderFilters = Depends(get_order_filters),
    db: Session = Depends(get_db),
) -> OrderKpiResponse:
    """Return the eight filtered Orders KPI values from PostgreSQL."""
    try:
        return OrdersService(OrdersRepository(db)).get_kpis(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve Orders KPI data")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve order KPI data."
        ) from error


@router.get("/charts", response_model=OrderChartsResponse)
def get_order_charts(
    filters: OrderFilters = Depends(get_order_filters),
    db: Session = Depends(get_db),
) -> OrderChartsResponse:
    """Return the four filtered ORD-002 chart datasets from PostgreSQL."""
    try:
        return OrdersService(OrdersRepository(db)).get_charts(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve Orders chart data")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve order chart data."
        ) from error


@router.get("/performance-insights", response_model=OrderPerformanceResponse)
def get_order_performance_insights(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str = Query(default="", max_length=100),
    sort_by: Literal[
        "order_date",
        "units_ordered",
        "fulfillment_status",
        "order_progress",
        "fulfillment_health",
    ] = Query(default="order_date"),
    sort_direction: Literal["asc", "desc"] = Query(default="desc"),
    filters: OrderFilters = Depends(get_order_filters),
    db: Session = Depends(get_db),
) -> OrderPerformanceResponse:
    """Return one paginated fulfillment detail per order."""
    try:
        return OrdersService(OrdersRepository(db)).get_performance_insights(
            filters,
            page,
            page_size,
            search,
            sort_by,
            sort_direction,
        )
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve Order Fulfillment Details")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve order fulfillment detail data.",
        ) from error


@router.get("/{order_id:path}/timeline", response_model=OrderTimelineResponse)
def get_order_timeline(
    order_id: str,
    db: Session = Depends(get_db),
) -> OrderTimelineResponse:
    """Return reliable stored events for one order in the configured shop."""
    try:
        response = OrdersService(OrdersRepository(db)).get_timeline(order_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve Order Timeline")
        raise HTTPException(
            status_code=500, detail="Unable to retrieve order timeline data."
        ) from error
    if response is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return response
