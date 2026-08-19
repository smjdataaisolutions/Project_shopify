from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class TopSellingProduct(BaseModel):
    product_id: str
    product_name: str
    image_url: str | None
    units_sold: int = Field(ge=0)


class ProductFilterOption(BaseModel):
    value: str
    label: str


class ProductFilterOptions(BaseModel):
    product_types: list[str]
    vendors: list[str]
    statuses: list[ProductFilterOption]


class ProductKpiResponse(BaseModel):
    total_products: int = Field(ge=0)
    total_variants: int = Field(ge=0)
    top_selling_product: TopSellingProduct | None
    products_with_no_sales: int = Field(ge=0)
    filter_options: ProductFilterOptions


class ProductUnitsSold(BaseModel):
    product_id: str
    product_name: str
    units_sold: int = Field(ge=1)


class ProductRevenue(BaseModel):
    product_id: str
    product_name: str
    revenue: Decimal = Field(ge=0)


class ProductDimensionRevenue(BaseModel):
    label: str
    revenue: Decimal = Field(ge=0)


class ProductSalesPerformanceResponse(BaseModel):
    top_selling: list[ProductUnitsSold]
    low_selling: list[ProductUnitsSold]
    sales_by_vendor: list[ProductDimensionRevenue]
    sales_by_product_type: list[ProductDimensionRevenue]
    product_revenue_contribution: list[ProductRevenue]
    currency: str | None


class ProductPerformanceItem(BaseModel):
    product_id: str
    product_name: str
    image_url: str | None
    status: str
    units_sold: int = Field(ge=0)
    revenue: Decimal = Field(ge=0)
    orders: int = Field(ge=0)
    inventory: int | None
    sales_velocity: float = Field(ge=0)
    performance: Literal["top_seller", "healthy", "slow_moving", "no_sales"]


class ProductPerformancePagination(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ProductPerformanceResponse(BaseModel):
    items: list[ProductPerformanceItem]
    pagination: ProductPerformancePagination
    reporting_days: int = Field(ge=1)
    currency: str | None
