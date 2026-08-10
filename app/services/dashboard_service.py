from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.repositories.dashboard_repository import DashboardRepository, OverviewFilters
from app.schemas.dashboard import (
    AffectedProduct,
    ActionNeededItem,
    ActionNeededResponse,
    BusinessHighlight,
    BusinessHighlightsResponse,
    DashboardSummary,
    InventoryHealthHighlight,
    InventoryHighlightMetrics,
    OverviewFilterOptionsResponse,
    SalesChannelFilterOption,
    SalesHighlightMetrics,
    SalesPerformanceHighlight,
    TopProductHighlightMetrics,
    TopSellingProductHighlight,
)
from app.services.sales_channel_service import group_sales_channels


MAX_ACTIONS = 5
ACTION_PRIORITY_ORDER = {"critical": 0, "warning": 1, "recommendation": 2}
SALES_CHANNEL_DESCRIPTIONS = {
    "online_store": "Order placed through the Shopify storefront",
    "point_of_sale": "Order created through Shopify POS",
    "shop": "Order originating from the Shop channel/app",
    "draft_orders": "Order created from a draft order",
    "facebook_instagram": "Order associated with Meta sales channels",
    "other_app_specific_channels": (
        "Orders created through installed apps or other integrations"
    ),
}


def build_overview_filters(
    start_date: date | None,
    end_date: date | None,
    financial_statuses: list[str] | None,
    fulfillment_statuses: list[str] | None,
    sales_channels: list[str] | None = None,
) -> OverviewFilters:
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    return OverviewFilters(
        start_date=start_date,
        end_date=end_date,
        financial_statuses=tuple(dict.fromkeys(financial_statuses or [])),
        fulfillment_statuses=tuple(dict.fromkeys(fulfillment_statuses or [])),
        sales_channels=tuple(dict.fromkeys(sales_channels or [])),
    )


def _build_sales_channel_options(
    source_names: tuple[str, ...],
) -> list[SalesChannelFilterOption]:
    return [
        SalesChannelFilterOption(
            id=category_id,
            name=name,
            description=SALES_CHANNEL_DESCRIPTIONS[category_id],
            values=values,
        )
        for category_id, name, values in group_sales_channels(source_names)
    ]


class DashboardService:
    """Business rules for deterministic Store Overview highlights."""

    def __init__(
        self,
        repository: DashboardRepository,
        low_stock_threshold: int,
    ) -> None:
        self.repository = repository
        self.low_stock_threshold = low_stock_threshold

    def get_summary(self, filters: OverviewFilters) -> DashboardSummary:
        metrics = self.repository.get_dashboard_summary(
            filters, self.low_stock_threshold
        )
        average_order_value = (
            metrics.total_revenue / metrics.total_orders
            if metrics.total_orders
            else Decimal("0")
        )
        return DashboardSummary(
            total_products=metrics.total_products,
            total_variants=metrics.total_variants,
            low_stock_products=metrics.low_stock_products,
            out_of_stock_products=metrics.out_of_stock_products,
            total_orders=metrics.total_orders,
            total_revenue=float(metrics.total_revenue),
            units_sold=metrics.units_sold,
            average_order_value=float(average_order_value),
        )

    def get_filter_options(self) -> OverviewFilterOptionsResponse:
        options = self.repository.get_filter_options()
        return OverviewFilterOptionsResponse(
            order_statuses=list(options.financial_statuses),
            fulfillment_statuses=list(options.fulfillment_statuses),
            sales_channels=_build_sales_channel_options(options.sales_channels),
        )

    def get_business_highlights(
        self, filters: OverviewFilters
    ) -> BusinessHighlightsResponse:
        sales = self.repository.get_sales_metrics(filters)
        inventory = self.repository.get_inventory_health(self.low_stock_threshold)
        top_product = self.repository.get_top_selling_product(filters)

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


class ActionNeededService:
    """Generate prioritized merchant actions from overview aggregates."""

    def __init__(
        self,
        repository: DashboardRepository,
        low_aov_threshold: Decimal,
        low_stock_threshold: int = 10,
    ) -> None:
        self.repository = repository
        self.low_aov_threshold = low_aov_threshold
        self.low_stock_threshold = low_stock_threshold

    def get_actions(
        self, filters: OverviewFilters = OverviewFilters()
    ) -> ActionNeededResponse:
        sales = self.repository.get_sales_metrics(filters)
        inventory = self.repository.get_inventory_health(self.low_stock_threshold)
        affected_inventory = []
        if inventory.out_of_stock_count > 0 or inventory.low_stock_count > 0:
            affected_inventory = self.repository.get_affected_inventory_products(
                self.low_stock_threshold
            )

        out_of_stock_products = [
            AffectedProduct(
                product_id=product.product_id,
                product_title=product.product_title or "Untitled product",
                inventory_quantity=0,
            )
            for product in affected_inventory
            if product.is_out_of_stock
        ]
        low_stock_products = [
            AffectedProduct(
                product_id=product.product_id,
                product_title=product.product_title or "Untitled product",
                inventory_quantity=product.low_stock_quantity,
            )
            for product in affected_inventory
            if product.low_stock_quantity is not None
        ]

        actions: list[ActionNeededItem] = []
        if inventory.out_of_stock_count > 0:
            count = inventory.out_of_stock_count
            actions.append(
                ActionNeededItem(
                    id="inventory_out_of_stock",
                    priority="critical",
                    category="inventory",
                    title="Products are out of stock",
                    message=(
                        f"{_format_count(count, 'product')} "
                        f"{_count_verb(count)} currently unavailable."
                    ),
                    affected_products=out_of_stock_products,
                    recommended_action="Restock inventory immediately.",
                )
            )

        if inventory.low_stock_count > 0:
            count = inventory.low_stock_count
            actions.append(
                ActionNeededItem(
                    id="inventory_low_stock",
                    priority="warning",
                    category="inventory",
                    title="Inventory is running low",
                    message=(
                        f"{_format_count(count, 'product')} "
                        f"{_count_verb(count)} between 1 and "
                        f"{self.low_stock_threshold} units remaining."
                    ),
                    affected_products=low_stock_products,
                    recommended_action="Plan inventory replenishment.",
                )
            )

        if sales.total_orders == 0:
            filtered_orders = filters.has_order_filters
            actions.append(
                ActionNeededItem(
                    id="sales_no_orders",
                    priority="warning",
                    category="sales",
                    title=(
                        "No orders match the selected filters"
                        if filtered_orders
                        else "No orders yet"
                    ),
                    message=(
                        "No orders were found for the selected date and statuses."
                        if filtered_orders
                        else "No orders have been recorded for this store."
                    ),
                    recommended_action=(
                        "Review store traffic and marketing activities."
                    ),
                )
            )
        elif sales.total_revenue is not None:
            average_order_value = sales.total_revenue / sales.total_orders
            if average_order_value < self.low_aov_threshold:
                actions.append(
                    ActionNeededItem(
                        id="sales_low_average_order_value",
                        priority="recommendation",
                        category="sales",
                        title="Average order value is low",
                        message=(
                            "Average order value is "
                            f"{_format_money(average_order_value, sales.currency_code)}, "
                            "below the configured threshold of "
                            f"{_format_money(self.low_aov_threshold, sales.currency_code)}."
                        ),
                        recommended_action=(
                            "Increase average order value using bundles or upsell offers."
                        ),
                    )
                )

        actions.sort(key=lambda action: ACTION_PRIORITY_ORDER[action.priority])
        return ActionNeededResponse(actions=actions[:MAX_ACTIONS])


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
