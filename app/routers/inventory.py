import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.inventory_repository import InventoryRepository
from app.schemas.inventory import InventoryKpiResponse
from app.services.inventory_service import InventoryService


router = APIRouter(prefix="/api/analytics/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)


@router.get("/kpis", response_model=InventoryKpiResponse)
def get_inventory_kpis(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> InventoryKpiResponse:
    """Return current inventory health and trailing-30-day velocity KPIs."""
    try:
        return InventoryService(
            InventoryRepository(db),
            settings.low_stock_threshold,
        ).get_kpis()
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve inventory KPIs")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve inventory KPI data.",
        ) from error
