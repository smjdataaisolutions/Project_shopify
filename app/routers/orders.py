from datetime import date
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.orders_repository import OrderFilters, OrdersRepository
from app.schemas.orders import OrderKpiResponse
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
