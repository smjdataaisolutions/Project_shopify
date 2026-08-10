from datetime import date
from typing import Literal

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


class RevenueTrendPoint(BaseModel):
    date: date
    revenue: float = Field(ge=0)


class RevenueTrendHighlights(BaseModel):
    total_revenue: float = Field(ge=0)
    highest_revenue_date: date
    highest_daily_revenue: float = Field(ge=0)


class RevenueTrendResponse(BaseModel):
    currency: str | None
    interval: Literal["daily"]
    data: list[RevenueTrendPoint]
    highlights: RevenueTrendHighlights | None


class SalesAction(BaseModel):
    id: str
    priority: Literal["critical", "warning", "recommendation"]
    category: Literal["sales"]
    title: str
    message: str
    recommended_action: str
    action_label: str
    action_url: str
    download_available: bool = False


class SalesActionNeededResponse(BaseModel):
    has_sufficient_data: bool
    actions: list[SalesAction]
