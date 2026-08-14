from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SalesSummary(BaseModel):
    gross_sales: float = Field(ge=0)
    discounts: float = Field(ge=0)
    returns_refunds: float = Field(ge=0)
    net_sales: float
    shipping: float = Field(ge=0)
    taxes: float = Field(ge=0)
    total_sales: float = Field(ge=0)
    orders_count: int = Field(ge=0)
    average_order_value: float = Field(ge=0)
    currency: str | None
    last_updated_at: datetime | None = None


class SalesChannelFilterOption(BaseModel):
    id: str
    name: str
    values: list[str]


class SalesFilterOptionsResponse(BaseModel):
    sales_channels: list[SalesChannelFilterOption]
    order_statuses: list[str]
    currencies: list[str]


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


class DailySalesBreakdownValues(BaseModel):
    gross_sales: float
    discounts: float
    returns_refunds: float
    net_sales: float
    shipping: float
    tax: float
    total_sales: float
    orders: int = Field(ge=0)
    average_order_value: float


class DailySalesBreakdownItem(DailySalesBreakdownValues):
    date: date


class DailySalesBreakdownPagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class DailySalesBreakdownSorting(BaseModel):
    sort_by: str
    sort_direction: Literal["asc", "desc"]


class DailySalesBreakdownResponse(BaseModel):
    currency: str | None
    items: list[DailySalesBreakdownItem]
    summary: DailySalesBreakdownValues
    pagination: DailySalesBreakdownPagination
    sorting: DailySalesBreakdownSorting
