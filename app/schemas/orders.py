from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class OrderKpiResponse(BaseModel):
    total_orders: int
    units_ordered: int
    unfulfilled_orders: int
    partially_fulfilled_orders: int
    fulfilled_orders: int
    cancelled_orders: int
    refunded_orders: int
    fulfillment_rate: float


class OrderTrendPoint(BaseModel):
    date: date
    orders: int = Field(ge=0)


class OrderFulfillmentStatusPoint(BaseModel):
    status: Literal["Fulfilled", "Unfulfilled", "Partially Fulfilled"]
    orders: int = Field(ge=0)


class OrderSalesChannelPoint(BaseModel):
    sales_channel: str
    orders: int = Field(ge=0)


class OrderStatusDistributionPoint(BaseModel):
    status: Literal["Fulfilled", "Unfulfilled", "Cancelled", "Refunded"]
    orders: int = Field(ge=0)


class OrderExceptionsPoint(BaseModel):
    date: date
    cancelled_orders: int = Field(ge=0)
    refunded_orders: int = Field(ge=0)


class OrderChartsResponse(BaseModel):
    granularity: Literal["day", "week", "month"]
    orders_trend: list[OrderTrendPoint]
    fulfillment_status: list[OrderFulfillmentStatusPoint]
    orders_by_sales_channel: list[OrderSalesChannelPoint]
    order_status_distribution: list[OrderStatusDistributionPoint]
    order_exceptions_trend: list[OrderExceptionsPoint]


class OrderPerformanceItem(BaseModel):
    order_id: str
    order_name: str
    order_date: datetime
    units_ordered: int = Field(ge=0)
    fulfillment_status: Literal[
        "cancelled", "fulfilled", "partially_fulfilled", "unfulfilled", "unknown"
    ]
    order_progress: Literal[
        "cancelled", "fulfilled", "in_progress", "open", "not_required", "unknown"
    ]
    order_progress_seconds: int | None = Field(default=None, ge=0)
    order_progress_label: str
    fulfillment_health: Literal[
        "healthy", "attention_needed", "critical", "cancelled", "unknown"
    ]
    fulfillment_health_reason: str | None
    shopify_admin_url: str | None


class OrderPerformancePagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class OrderPerformanceMeta(BaseModel):
    order_grain: Literal["one_order"] = "one_order"
    historical_fulfillment_time_supported: bool
    order_progress_age_supported: bool
    not_required_supported: bool


class OrderPerformanceResponse(BaseModel):
    items: list[OrderPerformanceItem]
    pagination: OrderPerformancePagination
    meta: OrderPerformanceMeta


class OrderTimelineEvent(BaseModel):
    event_type: Literal[
        "order_created", "order_processed", "order_cancelled", "refund_recorded"
    ]
    title: str
    occurred_at: datetime
    description: str | None
    amount: float | None


class OrderTimelineCurrentStatus(BaseModel):
    payment_status: str | None
    fulfillment_status: str | None
    fulfillment_timestamp_available: Literal[False] = False


class OrderTimelineResponse(BaseModel):
    order_id: str
    order_name: str
    events: list[OrderTimelineEvent]
    current_status: OrderTimelineCurrentStatus
    currency: str | None
