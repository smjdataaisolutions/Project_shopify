import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.inventory_repository import InventoryFilters, InventoryRepository
from app.schemas.inventory import (
    InventoryFilterOptionsResponse,
    InventoryKpiResponse,
    InventoryTableResponse,
)
from app.services.inventory_service import InventoryService, build_inventory_filters


router = APIRouter(prefix="/api/analytics/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)


def get_inventory_filters(
    product_id: list[str] | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    location_id: list[str] | None = Query(default=None),
    vendor: list[str] | None = Query(default=None),
    collection_id: list[str] | None = Query(default=None),
    inventory_tracked: bool | None = Query(default=None),
    inventory_status: list[str] | None = Query(default=None),
) -> InventoryFilters:
    try:
        return build_inventory_filters(
            product_ids=product_id,
            start_date=start_date,
            end_date=end_date,
            location_ids=location_id,
            vendors=vendor,
            collection_ids=collection_id,
            inventory_tracked=inventory_tracked,
            inventory_statuses=inventory_status,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/filter-options", response_model=InventoryFilterOptionsResponse)
def get_inventory_filter_options(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InventoryFilterOptionsResponse:
    """Return available filters and explicit unsupported-filter capabilities."""
    try:
        return InventoryService(
            InventoryRepository(db),
            settings.low_stock_threshold,
        ).get_filter_options()
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve inventory filter options")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve inventory filter options.",
        ) from error


@router.get("/kpis", response_model=InventoryKpiResponse)
def get_inventory_kpis(
    level: Literal["product", "variant"] = "variant",
    filters: InventoryFilters = Depends(get_inventory_filters),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InventoryKpiResponse:
    """Return current inventory health and trailing-30-day velocity KPIs."""
    try:
        return InventoryService(
            InventoryRepository(db),
            settings.low_stock_threshold,
        ).get_kpis(filters, level)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve inventory KPIs")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve inventory KPI data.",
        ) from error


@router.get("/table", response_model=InventoryTableResponse)
def get_inventory_table(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
    level: Literal["product", "variant"] = "variant",
    filters: InventoryFilters = Depends(get_inventory_filters),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InventoryTableResponse:
    """Return a paginated current inventory row per variant and location."""
    try:
        return InventoryService(
            InventoryRepository(db),
            settings.low_stock_threshold,
        ).get_inventory_table(page, page_size, sort_order, filters, level)
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve the inventory table")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve inventory table data.",
        ) from error


@router.get("/table/download")
def download_inventory_table(
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
    level: Literal["product", "variant"] = "variant",
    filters: InventoryFilters = Depends(get_inventory_filters),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Download all current Inventory details rows as CSV."""
    try:
        export = InventoryService(
            InventoryRepository(db),
            settings.low_stock_threshold,
        ).get_inventory_table_export(sort_order, filters, level)
        return Response(
            content=export.content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{export.filename}"'
            },
        )
    except SQLAlchemyError as error:
        logger.exception("Unable to export the inventory table")
        raise HTTPException(
            status_code=500,
            detail="Unable to export inventory table data.",
        ) from error
