from typing import Literal

from pydantic import BaseModel, Field


class InventoryKpiResponse(BaseModel):
    total_inventory_units: int = Field(ge=0)
    in_stock_products: int = Field(ge=0)
    low_stock_products: int = Field(ge=0)
    out_of_stock_products: int = Field(ge=0)
    sell_through_rate: float | None = Field(default=None, ge=0, le=100)
    days_of_inventory_remaining: float | None = Field(default=None, ge=0)


class InventoryTableItem(BaseModel):
    variant_id: str
    location_id: str | None
    product_variant_name: str
    inventory_units: int | None
    location: str | None
    inventory_tracked: bool
    inventory_status: Literal[
        "healthy",
        "low_stock",
        "out_of_stock",
        "negative",
        "untracked",
        "unknown",
    ]


class InventoryTablePagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class InventoryTableTotals(BaseModel):
    total_inventory_units: int = Field(ge=0)


class InventoryTableResponse(BaseModel):
    items: list[InventoryTableItem]
    pagination: InventoryTablePagination
    totals: InventoryTableTotals
