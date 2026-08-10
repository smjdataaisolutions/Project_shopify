from datetime import date
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.sales_repository import SalesRepository
from app.schemas.sales import (
    RevenueTrendResponse,
    SalesActionNeededResponse,
    SalesSummary,
)
from app.services.sales_service import SalesService


router = APIRouter(prefix="/api/sales", tags=["sales"])
logger = logging.getLogger(__name__)


@router.get("/summary", response_model=SalesSummary)
def get_sales_summary(
    db: Session = Depends(get_db),
) -> SalesSummary:
    """Return aggregate sales metrics with one PostgreSQL table scan."""
    return SalesService(SalesRepository(db)).get_sales_summary()


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


@router.get("/action-needed", response_model=SalesActionNeededResponse)
def get_sales_action_needed(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
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
        return service.get_action_needed(start_date, end_date)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve sales action needed recommendations")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve sales action needed recommendations.",
        ) from error


@router.get("/action-needed/{action_id}/download")
def download_sales_action_needed_records(
    action_id: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Download the PostgreSQL records contributing to a supported action."""
    try:
        export = SalesService(SalesRepository(db)).get_action_export(
            action_id, start_date, end_date
        )
        return Response(
            content=export.content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{export.filename}"'
            },
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Unable to export sales action needed records")
        raise HTTPException(
            status_code=500,
            detail="Unable to export sales action needed records.",
        ) from error
