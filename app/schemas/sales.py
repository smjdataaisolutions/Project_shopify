from pydantic import BaseModel, Field


class SalesSummary(BaseModel):
    gross_sales: float = Field(ge=0)
    discounts: float = Field(ge=0)
    net_sales: float = Field(ge=0)
    shipping: float = Field(ge=0)
    taxes: float = Field(ge=0)
    total_sales: float = Field(ge=0)
    orders_count: int = Field(ge=0)
    average_order_value: float = Field(ge=0)
