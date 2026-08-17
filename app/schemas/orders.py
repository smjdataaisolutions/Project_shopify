from pydantic import BaseModel


class OrderKpiResponse(BaseModel):
    total_orders: int
    units_ordered: int
    unfulfilled_orders: int
    partially_fulfilled_orders: int
    fulfilled_orders: int
    cancelled_orders: int
    refunded_orders: int
    fulfillment_rate: float
