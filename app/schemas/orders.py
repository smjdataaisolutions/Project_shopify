from datetime import date
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
