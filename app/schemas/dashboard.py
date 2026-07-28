from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    total_products: int = Field(ge=0)
    total_variants: int = Field(ge=0)
    low_stock_products: int = Field(ge=0)
    out_of_stock_products: int = Field(ge=0)
    total_orders: int = Field(ge=0)
    total_revenue: float = Field(ge=0)
    units_sold: int = Field(ge=0)
    average_order_value: float = Field(ge=0)
