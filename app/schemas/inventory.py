from pydantic import BaseModel, Field


class InventoryKpiResponse(BaseModel):
    total_inventory_units: int = Field(ge=0)
    in_stock_products: int = Field(ge=0)
    low_stock_products: int = Field(ge=0)
    out_of_stock_products: int = Field(ge=0)
    sell_through_rate: float | None = Field(default=None, ge=0, le=100)
    days_of_inventory_remaining: float | None = Field(default=None, ge=0)
