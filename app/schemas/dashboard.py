from typing import Literal

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


class SalesHighlightMetrics(BaseModel):
    total_revenue: float = Field(ge=0)
    total_orders: int = Field(ge=0)
    average_order_value: float = Field(ge=0)


class InventoryHighlightMetrics(BaseModel):
    low_stock_count: int = Field(ge=0)
    out_of_stock_count: int = Field(ge=0)


class TopProductHighlightMetrics(BaseModel):
    product_id: str
    variant_id: str | None = None
    product_title: str
    units_sold: int = Field(ge=0)
    product_revenue: float = Field(ge=0)


class SalesPerformanceHighlight(BaseModel):
    id: Literal["sales_performance"]
    category: Literal["sales"]
    severity: Literal["info"]
    title: str
    message: str
    supporting_text: str | None
    metrics: SalesHighlightMetrics


class InventoryHealthHighlight(BaseModel):
    id: Literal["inventory_health"]
    category: Literal["inventory"]
    severity: Literal["positive", "warning", "critical"]
    title: str
    message: str
    supporting_text: str | None
    metrics: InventoryHighlightMetrics


class TopSellingProductHighlight(BaseModel):
    id: Literal["top_selling_product"]
    category: Literal["products"]
    severity: Literal["info"]
    title: str
    message: str
    supporting_text: str | None
    metrics: TopProductHighlightMetrics


BusinessHighlight = (
    SalesPerformanceHighlight
    | InventoryHealthHighlight
    | TopSellingProductHighlight
)


class BusinessHighlightsResponse(BaseModel):
    currency_code: str | None
    highlights: list[BusinessHighlight]
