import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.products_repository import ProductFilters, ProductsRepository
from app.schemas.products import (
    ProductKpiResponse,
    ProductPerformanceResponse,
    ProductSalesPerformanceResponse,
)
from app.services.products_service import ProductsService, build_product_filters


router = APIRouter(prefix="/api/products", tags=["products"])
logger = logging.getLogger(__name__)


def get_product_filters(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    product_type: list[str] = Query(default=[]),
    vendor: list[str] = Query(default=[]),
    status: list[str] = Query(default=[]),
) -> ProductFilters:
    try:
        return build_product_filters(
            start_date, end_date, product_type, vendor, status
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/kpis", response_model=ProductKpiResponse)
def get_product_kpis(
    response: Response,
    filters: ProductFilters = Depends(get_product_filters),
    db: Session = Depends(get_db),
) -> ProductKpiResponse:
    """Return current-catalog and all-time product-sales KPIs."""
    try:
        result = ProductsService(ProductsRepository(db)).get_kpis(filters)
        response.headers["Cache-Control"] = "no-store"
        return result
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve Product KPIs")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve product KPI data.",
        ) from error


@router.get(
    "/sales-performance",
    response_model=ProductSalesPerformanceResponse,
)
def get_product_sales_performance(
    response: Response,
    filters: ProductFilters = Depends(get_product_filters),
    db: Session = Depends(get_db),
) -> ProductSalesPerformanceResponse:
    """Return the top and low positive-unit product sales rankings."""
    try:
        result = ProductsService(ProductsRepository(db)).get_sales_performance(filters)
        response.headers["Cache-Control"] = "no-store"
        return result
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve Product sales performance")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve product sales performance data.",
        ) from error


@router.get("/performance", response_model=ProductPerformanceResponse)
def get_product_performance(
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str = Query(default="", max_length=200),
    sort_by: Literal[
        "product",
        "units_sold",
        "revenue",
        "orders",
        "inventory",
        "sales_velocity",
        "performance",
    ] = Query(default="units_sold"),
    sort_direction: Literal["asc", "desc"] = Query(default="desc"),
    filters: ProductFilters = Depends(get_product_filters),
    db: Session = Depends(get_db),
) -> ProductPerformanceResponse:
    """Return filtered product master, sales, and current inventory performance."""
    try:
        result = ProductsService(ProductsRepository(db)).get_performance_table(
            filters,
            page,
            page_size,
            search,
            sort_by,
            sort_direction,
        )
        response.headers["Cache-Control"] = "no-store"
        return result
    except SQLAlchemyError as error:
        logger.exception("Unable to retrieve Product performance table")
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve product performance data.",
        ) from error
