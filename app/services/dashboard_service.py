from decimal import Decimal, ROUND_HALF_UP

from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import (
    BusinessHighlight,
    BusinessHighlightsResponse,
    InventoryHealthHighlight,
    InventoryHighlightMetrics,
    SalesHighlightMetrics,
    SalesPerformanceHighlight,
    TopProductHighlightMetrics,
    TopSellingProductHighlight,
)


LOW_STOCK_THRESHOLD = 10


class DashboardService:
    """Business rules for deterministic Store Overview highlights."""

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    def get_business_highlights(self) -> BusinessHighlightsResponse:
        sales = self.repository.get_sales_metrics()
        inventory = self.repository.get_inventory_health(LOW_STOCK_THRESHOLD)
        top_product = self.repository.get_top_selling_product()

        highlights: list[BusinessHighlight] = []
        if sales.total_orders > 0 and sales.total_revenue is not None:
            total_revenue = _round_money(sales.total_revenue)
            average_order_value = _round_money(
                sales.total_revenue / sales.total_orders
            )
            highlights.append(
                SalesPerformanceHighlight(
                    id="sales_performance",
                    category="sales",
                    severity="info",
                    title="Sales performance",
                    message=(
                        f"{_format_money(total_revenue, sales.currency_code)} "
                        f"in revenue was generated from "
                        f"{_format_count(sales.total_orders, 'order')}."
                    ),
                    supporting_text=(
                        "Average order value was "
                        f"{_format_money(average_order_value, sales.currency_code)}."
                    ),
                    metrics=SalesHighlightMetrics(
                        total_revenue=float(total_revenue),
                        total_orders=sales.total_orders,
                        average_order_value=float(average_order_value),
                    ),
                )
            )

        if inventory.products_with_inventory > 0:
            severity = "positive"
            if inventory.out_of_stock_count > 0:
                severity = "critical"
            elif inventory.low_stock_count > 0:
                severity = "warning"

            highlights.append(
                InventoryHealthHighlight(
                    id="inventory_health",
                    category="inventory",
                    severity=severity,
                    title="Inventory health",
                    message=_inventory_message(
                        inventory.low_stock_count, inventory.out_of_stock_count
                    ),
                    supporting_text=None,
                    metrics=InventoryHighlightMetrics(
                        low_stock_count=inventory.low_stock_count,
                        out_of_stock_count=inventory.out_of_stock_count,
                    ),
                )
            )

        if top_product is not None:
            product_title = top_product.product_title or "Untitled product"
            product_revenue = _round_money(top_product.product_revenue)
            supporting_text = (
                "Product revenue was "
                f"{_format_money(product_revenue, top_product.currency_code)}."
            )
            highlights.append(
                TopSellingProductHighlight(
                    id="top_selling_product",
                    category="products",
                    severity="info",
                    title="Top-selling product",
                    message=(
                        f"{product_title} is the top-selling product with "
                        f"{_format_count(top_product.units_sold, 'unit')} sold."
                    ),
                    supporting_text=supporting_text,
                    metrics=TopProductHighlightMetrics(
                        product_id=top_product.product_id,
                        product_title=product_title,
                        units_sold=top_product.units_sold,
                        product_revenue=float(product_revenue),
                    ),
                )
            )

        currency_code = sales.currency_code or (
            top_product.currency_code if top_product else None
        )
        return BusinessHighlightsResponse(
            currency_code=currency_code,
            highlights=highlights,
        )


def _format_money(amount: Decimal, currency_code: str | None) -> str:
    formatted = f"{_round_money(amount):,.2f}"
    return f"{currency_code} {formatted}" if currency_code else formatted


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_count(value: int, noun: str) -> str:
    suffix = "" if value == 1 else "s"
    return f"{value:,} {noun}{suffix}"


def _inventory_message(low_stock_count: int, out_of_stock_count: int) -> str:
    if low_stock_count == 0 and out_of_stock_count == 0:
        return "No low-stock or out-of-stock products were found."
    if low_stock_count > 0 and out_of_stock_count > 0:
        return (
            f"{_format_count(low_stock_count, 'product')} "
            f"{_count_verb(low_stock_count)} running low in stock and "
            f"{_format_count(out_of_stock_count, 'product')} "
            f"{_count_verb(out_of_stock_count)} out of stock."
        )
    if low_stock_count > 0:
        return (
            f"{_format_count(low_stock_count, 'product')} "
            f"{_count_verb(low_stock_count)} running low in stock."
        )
    return (
        f"{_format_count(out_of_stock_count, 'product')} "
        f"{_count_verb(out_of_stock_count)} out of stock."
    )


def _count_verb(value: int) -> str:
    return "is" if value == 1 else "are"
