from datetime import date, datetime
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
    last_updated_at: datetime | None = None


class DailyStorePerformanceItem(BaseModel):
    date: date
    total_sales: float
    orders: int = Field(ge=0)
    units_sold: int
    average_order_value: float


class DailyStorePerformanceSummary(BaseModel):
    total_sales: float
    orders: int = Field(ge=0)
    units_sold: int
    average_order_value: float


class DailyStorePerformancePagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class DailyStorePerformanceResponse(BaseModel):
    currency_code: str | None
    items: list[DailyStorePerformanceItem]
    summary: DailyStorePerformanceSummary
    pagination: DailyStorePerformancePagination


class LastSevenDaysPeriod(BaseModel):
    time_zone: Literal["UTC"]
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date


class LastSevenDaysOrderItem(BaseModel):
    date: date
    orders: int = Field(ge=0)
    units_sold: int


class LastSevenDaysOrders(BaseModel):
    total_orders: int = Field(ge=0)
    items: list[LastSevenDaysOrderItem]


class LastSevenDaysProductItem(BaseModel):
    product_id: str
    product_name: str
    units_sold: int
    orders: int = Field(ge=0)
    net_product_sales: float


class LastSevenDaysTopProducts(BaseModel):
    items: list[LastSevenDaysProductItem]


class LastSevenDaysSalesComparison(BaseModel):
    current_total_sales: float
    previous_total_sales: float
    percentage_change: float | None
    status: Literal["increase", "decline", "no_change", "new_activity"]


class LastSevenDaysPerformanceResponse(BaseModel):
    period: LastSevenDaysPeriod
    orders_by_day: LastSevenDaysOrders
    top_selling_products: LastSevenDaysTopProducts
    total_revenue_comparison: LastSevenDaysSalesComparison
    currency_code: str | None


class SalesChannelFilterOption(BaseModel):
    id: Literal[
        "online_store",
        "point_of_sale",
        "shop",
        "draft_orders",
        "facebook_instagram",
        "other_app_specific_channels",
    ]
    name: str
    description: str
    values: list[str]


class OverviewFilterOptionsResponse(BaseModel):
    order_statuses: list[str]
    fulfillment_statuses: list[str]
    sales_channels: list[SalesChannelFilterOption]


class ComparisonPeriodMetrics(BaseModel):
    start_date: date
    end_date: date
    total_sales: float
    orders: int = Field(ge=0)
    average_order_value: float


class SalesMomentumHighlight(BaseModel):
    id: Literal["sales_momentum"]
    title: Literal["Sales Momentum"]
    status: Literal[
        "positive",
        "attention",
        "stable",
        "new_activity",
        "no_activity",
        "unavailable",
    ]
    message: str
    supporting_text: str | None
    helper_text: str | None = None
    action_label: Literal["View daily performance"]
    current_period: ComparisonPeriodMetrics | None
    previous_period: ComparisonPeriodMetrics | None
    total_sales_change_percentage: float | None
    order_change: int | None
    order_change_percentage: float | None
    aov_change_percentage: float | None


class ProductConcentrationProduct(BaseModel):
    product_id: str
    product_name: str
    net_product_sales: float
    units_sold: int
    contribution_percentage: float | None


class ProductSalesConcentrationHighlight(BaseModel):
    id: Literal["product_sales_concentration"]
    title: Literal["Product Sales Concentration"]
    status: Literal["high", "moderate", "diversified", "unavailable"]
    message: str
    supporting_text: str | None
    helper_text: str | None = None
    action_label: Literal["View top products"]
    top_product: ProductConcentrationProduct | None
    products_in_top_group: int = Field(ge=0)
    top_group_net_product_sales: float | None
    top_group_contribution_percentage: float | None
    total_net_product_sales: float | None


class InventoryExposureProduct(BaseModel):
    product_id: str
    product_name: str
    inventory_status: Literal["low_stock", "out_of_stock"]
    net_product_sales: float
    units_sold: int


class InventoryExposureHighlight(BaseModel):
    id: Literal["inventory_exposure"]
    title: Literal["Inventory Exposure"]
    status: Literal["critical", "warning", "healthy", "unavailable"]
    message: str
    supporting_text: str | None
    helper_text: str
    action_label: Literal["Review affected products"]
    affected_product_count: int = Field(ge=0)
    low_stock_product_count: int = Field(ge=0)
    out_of_stock_product_count: int = Field(ge=0)
    affected_net_product_sales: float | None
    affected_units_sold: int | None
    highest_impact_product: InventoryExposureProduct | None
    inventory_as_of: str | None


class BusinessHighlightsResponse(BaseModel):
    currency_code: str | None
    highlights: list[
        SalesMomentumHighlight
        | ProductSalesConcentrationHighlight
        | InventoryExposureHighlight
    ]


class AffectedProduct(BaseModel):
    product_id: str
    product_title: str
    inventory_quantity: int = Field(ge=0)


class ActionNeededItem(BaseModel):
    id: Literal[
        "inventory_out_of_stock",
        "inventory_low_stock",
        "sales_no_orders",
        "sales_low_average_order_value",
    ]
    priority: Literal["critical", "warning", "recommendation"]
    category: Literal["inventory", "orders", "products", "sales"]
    title: str
    message: str
    affected_products: list[AffectedProduct] = Field(default_factory=list)
    recommended_action: str
    action_label: str
    action_url: str
    download_available: bool = True


class ActionNeededResponse(BaseModel):
    actions: list[ActionNeededItem]
