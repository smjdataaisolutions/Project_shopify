from datetime import date
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.dashboard_repository import DashboardRepository, OverviewFilters
from app.schemas.dashboard import (
    ActionNeededResponse,
    BusinessHighlightsResponse,
    DashboardSummary,
    OverviewFilterOptionsResponse,
)
from app.services.dashboard_service import (
    ActionNeededService,
    DashboardService,
    build_overview_filters,
)


router = APIRouter(prefix="/api", tags=["dashboard"])
logger = logging.getLogger(__name__)


def get_overview_filters(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    financial_status: Annotated[list[str] | None, Query()] = None,
    fulfillment_status: Annotated[list[str] | None, Query()] = None,
) -> OverviewFilters:
    try:
        return build_overview_filters(
            start_date,
            end_date,
            financial_status,
            fulfillment_status,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _dashboard_service(db: Session) -> DashboardService:
    return DashboardService(
        DashboardRepository(db),
        low_stock_threshold=get_settings().low_stock_threshold,
    )


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(
    filters: OverviewFilters = Depends(get_overview_filters),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """Return Store Overview KPI values for the selected filters."""
    try:
        return _dashboard_service(db).get_summary(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve the store overview")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve store performance overview.",
        ) from error


@router.get(
    "/analytics/overview/filter-options",
    response_model=OverviewFilterOptionsResponse,
)
def get_overview_filter_options(
    db: Session = Depends(get_db),
) -> OverviewFilterOptionsResponse:
    """Return exact filter values available in synchronized PostgreSQL data."""
    try:
        return _dashboard_service(db).get_filter_options()
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve overview filter options")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve overview filter options.",
        ) from error


@router.get(
    "/analytics/overview/business-highlights",
    response_model=BusinessHighlightsResponse,
)
def get_business_highlights(
    filters: OverviewFilters = Depends(get_overview_filters),
    db: Session = Depends(get_db),
) -> BusinessHighlightsResponse:
    """Return rule-based highlights for the selected filters."""
    try:
        return _dashboard_service(db).get_business_highlights(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve overview business highlights")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve business highlights.",
        ) from error


@router.get(
    "/analytics/overview/action-needed",
    response_model=ActionNeededResponse,
)
def get_action_needed(
    filters: OverviewFilters = Depends(get_overview_filters),
    db: Session = Depends(get_db),
) -> ActionNeededResponse:
    """Return prioritized actions for the selected filters."""
    try:
        settings = get_settings()
        service = ActionNeededService(
            DashboardRepository(db),
            low_aov_threshold=settings.low_aov_threshold,
            low_stock_threshold=settings.low_stock_threshold,
        )
        return service.get_actions(filters)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve overview actions")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve action needed recommendations.",
        ) from error
