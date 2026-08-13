import csv
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import io
from collections.abc import Callable

from app.repositories.dashboard_repository import DashboardRepository, OverviewFilters
from app.schemas.dashboard import (
    AffectedProduct,
    ActionNeededItem,
    ActionNeededResponse,
    BusinessHighlightsResponse,
    ComparisonPeriodMetrics,
    DashboardSummary,
    DailyStorePerformanceItem,
    DailyStorePerformancePagination,
    DailyStorePerformanceResponse,
    DailyStorePerformanceSummary,
    InventoryExposureHighlight,
    InventoryExposureProduct,
    LastSevenDaysOrderItem,
    LastSevenDaysOrders,
    LastSevenDaysPerformanceResponse,
    LastSevenDaysPeriod,
    LastSevenDaysProductItem,
    LastSevenDaysSalesComparison,
    LastSevenDaysTopProducts,
    OverviewFilterOptionsResponse,
    SalesChannelFilterOption,
    ProductConcentrationProduct,
    ProductSalesConcentrationHighlight,
    SalesMomentumHighlight,
)
from app.services.sales_channel_service import group_sales_channels


MAX_ACTIONS = 5
SALES_MOMENTUM_CHANGE_THRESHOLD = Decimal("5")
HIGH_PRODUCT_CONCENTRATION_THRESHOLD = Decimal("50")
MODERATE_PRODUCT_CONCENTRATION_THRESHOLD = Decimal("30")
ACTION_PRIORITY_ORDER = {"critical": 0, "warning": 1, "recommendation": 2}
INVENTORY_CSV_COLUMNS = (
    "product_id",
    "affected_product_name",
    "variant_title",
    "sku",
    "inventory_quantity",
    "location_name",
    "units_sold",
    "issue_type",
    "issue_value",
)
ORDER_CSV_COLUMNS = (
    "order_id",
    "order_number",
    "product_name",
    "financial_status",
    "fulfillment_status",
    "order_amount",
    "issue_type",
    "issue_value",
)
SALES_CSV_COLUMNS = (
    "order_id",
    "product_name",
    "units",
    "gross_sales",
    "discount_amount",
    "net_sales",
    "issue_type",
    "issue_value",
)
ACTION_METADATA = {
    "inventory_out_of_stock": {
        "category": "inventory",
        "action_label": "Go to Inventory",
        "action_url": "/app/inventory",
        "filename": "out_of_stock_products.csv",
        "columns": INVENTORY_CSV_COLUMNS,
    },
    "inventory_low_stock": {
        "category": "inventory",
        "action_label": "Go to Inventory",
        "action_url": "/app/inventory",
        "filename": "low_stock_products.csv",
        "columns": INVENTORY_CSV_COLUMNS,
    },
    "sales_no_orders": {
        "category": "orders",
        "action_label": "Go to Orders",
        "action_url": "/app/orders",
        "filename": "order_issues.csv",
        "columns": ORDER_CSV_COLUMNS,
    },
    "sales_low_average_order_value": {
        "category": "sales",
        "action_label": "Go to Sales",
        "action_url": "/app/sales",
        "filename": "low_average_order_value_sales.csv",
        "columns": SALES_CSV_COLUMNS,
    },
}
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


@dataclass(frozen=True)
class OverviewActionCsvExport:
    filename: str
    content: str


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
        today: Callable[[], date] | None = None,
    ) -> None:
        self.repository = repository
        self.low_stock_threshold = low_stock_threshold
        self.today = today or (lambda: datetime.now(timezone.utc).date())

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
            last_updated_at=metrics.last_updated_at,
        )

    def get_daily_store_performance(
        self,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
        filters: OverviewFilters,
    ) -> DailyStorePerformanceResponse:
        result = self.repository.get_daily_store_performance(
            page,
            page_size,
            sort_by,
            sort_order,
            filters,
        )
        total_aov = (
            result.total_sales / result.total_orders
            if result.total_orders
            else Decimal("0")
        )
        return DailyStorePerformanceResponse(
            currency_code=result.currency_code,
            items=[
                DailyStorePerformanceItem(
                    date=row.date,
                    total_sales=float(_round_money(row.total_sales)),
                    orders=row.orders,
                    units_sold=row.units_sold,
                    average_order_value=float(
                        _round_money(
                            row.total_sales / row.orders
                            if row.orders
                            else Decimal("0")
                        )
                    ),
                )
                for row in result.rows
            ],
            summary=DailyStorePerformanceSummary(
                total_sales=float(_round_money(result.total_sales)),
                orders=result.total_orders,
                units_sold=result.total_units_sold,
                average_order_value=float(_round_money(total_aov)),
            ),
            pagination=DailyStorePerformancePagination(
                page=page,
                page_size=page_size,
                total_items=result.total_items,
                total_pages=(
                    (result.total_items + page_size - 1) // page_size
                    if result.total_items
                    else 0
                ),
            ),
        )

    def get_last_seven_days_performance(
        self,
        filters: OverviewFilters,
    ) -> LastSevenDaysPerformanceResponse:
        """Return the fixed UTC rolling seven-day charts and prior comparison."""
        current_end = self.today()
        current_start = current_end - timedelta(days=6)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
        current_start_at = datetime.combine(
            current_start,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        current_end_at = datetime.combine(
            current_end,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        previous_start_at = datetime.combine(
            previous_start,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        previous_end_at = datetime.combine(
            previous_end,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        non_date_filters = replace(filters, start_date=None, end_date=None)
        current_filters = replace(
            non_date_filters,
            start_date=current_start_at,
            end_date=current_end_at,
        )
        previous_filters = replace(
            non_date_filters,
            start_date=previous_start_at,
            end_date=previous_end_at,
        )

        daily = self.repository.get_daily_store_performance(
            1,
            7,
            "date",
            "asc",
            current_filters,
        )
        daily_by_date = {row.date: row for row in daily.rows}
        order_items = []
        for day_offset in range(7):
            item_date = current_start + timedelta(days=day_offset)
            row = daily_by_date.get(item_date)
            order_items.append(
                LastSevenDaysOrderItem(
                    date=item_date,
                    orders=row.orders if row else 0,
                    units_sold=row.units_sold if row else 0,
                )
            )

        top_products = self.repository.get_top_products_by_units(current_filters, 5)
        current_sales = self.repository.get_sales_metrics(current_filters)
        previous_sales = self.repository.get_sales_metrics(previous_filters)
        current_total = current_sales.total_revenue or Decimal("0")
        previous_total = previous_sales.total_revenue or Decimal("0")
        percentage_change = _percentage_change(current_total, previous_total)
        if current_total == 0 and previous_total == 0:
            comparison_status = "no_change"
        elif previous_total == 0:
            comparison_status = "new_activity"
        elif current_total < previous_total:
            comparison_status = "decline"
        elif current_total > previous_total:
            comparison_status = "increase"
        else:
            comparison_status = "no_change"

        return LastSevenDaysPerformanceResponse(
            period=LastSevenDaysPeriod(
                time_zone="UTC",
                current_start=current_start,
                current_end=current_end,
                previous_start=previous_start,
                previous_end=previous_end,
            ),
            orders_by_day=LastSevenDaysOrders(
                total_orders=sum(item.orders for item in order_items),
                items=order_items,
            ),
            top_selling_products=LastSevenDaysTopProducts(
                items=[
                    LastSevenDaysProductItem(
                        product_id=product.product_id,
                        product_name=product.product_title or "Untitled product",
                        units_sold=product.units_sold,
                        orders=product.orders,
                        net_product_sales=float(
                            _round_money(product.net_product_sales)
                        ),
                    )
                    for product in top_products
                ]
            ),
            total_revenue_comparison=LastSevenDaysSalesComparison(
                current_total_sales=float(_round_money(current_total)),
                previous_total_sales=float(_round_money(previous_total)),
                percentage_change=_optional_float(percentage_change),
                status=comparison_status,
            ),
            currency_code=(
                current_sales.currency_code
                or previous_sales.currency_code
                or daily.currency_code
            ),
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
        sales_momentum, sales_currency = self._build_sales_momentum(filters)
        concentration_result = self.repository.get_product_sales_concentration(
            filters
        )
        concentration = self._build_product_sales_concentration(
            concentration_result
        )
        exposure_result = self.repository.get_inventory_exposure(
            self.low_stock_threshold,
            filters,
        )
        exposure = self._build_inventory_exposure(exposure_result)
        currency_code = (
            sales_currency
            or concentration_result.currency_code
            or exposure_result.currency_code
        )
        return BusinessHighlightsResponse(
            currency_code=currency_code,
            highlights=[sales_momentum, concentration, exposure],
        )

    def _build_sales_momentum(
        self,
        filters: OverviewFilters,
    ) -> tuple[SalesMomentumHighlight, str | None]:
        if filters.start_date is None or filters.end_date is None:
            current = self.repository.get_sales_metrics(filters)
            return (
                SalesMomentumHighlight(
                    id="sales_momentum",
                    title="Sales Momentum",
                    status="unavailable",
                    message=(
                        "Select a complete date range to compare sales with the "
                        "immediately preceding period."
                    ),
                    supporting_text=None,
                    helper_text=(
                        "The previous period uses the same number of inclusive "
                        "calendar days."
                    ),
                    action_label="View daily performance",
                    current_period=None,
                    previous_period=None,
                    total_sales_change_percentage=None,
                    order_change=None,
                    order_change_percentage=None,
                    aov_change_percentage=None,
                ),
                current.currency_code,
            )

        period_days = (filters.end_date - filters.start_date).days + 1
        previous_end = filters.start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_days - 1)
        previous_filters = replace(
            filters,
            start_date=previous_start,
            end_date=previous_end,
        )
        current_sales = self.repository.get_sales_metrics(filters)
        previous_sales = self.repository.get_sales_metrics(previous_filters)
        current_revenue = current_sales.total_revenue or Decimal("0")
        previous_revenue = previous_sales.total_revenue or Decimal("0")
        current_aov = (
            current_revenue / current_sales.total_orders
            if current_sales.total_orders
            else Decimal("0")
        )
        previous_aov = (
            previous_revenue / previous_sales.total_orders
            if previous_sales.total_orders
            else Decimal("0")
        )
        revenue_change = _percentage_change(current_revenue, previous_revenue)
        order_change = current_sales.total_orders - previous_sales.total_orders
        order_change_percentage = _percentage_change(
            Decimal(current_sales.total_orders),
            Decimal(previous_sales.total_orders),
        )
        aov_change = _percentage_change(current_aov, previous_aov)

        if current_revenue == 0 and current_sales.total_orders == 0:
            status = (
                "no_activity"
                if previous_revenue == 0 and previous_sales.total_orders == 0
                else "attention"
            )
            message = "No sales activity was recorded in the selected period."
        elif previous_revenue == 0 and current_revenue > 0:
            status = "new_activity"
            message = "Sales activity started in the selected period."
        else:
            comparable_change = revenue_change or Decimal("0")
            if comparable_change >= SALES_MOMENTUM_CHANGE_THRESHOLD:
                status = "positive"
                movement = "increased"
            elif comparable_change <= -SALES_MOMENTUM_CHANGE_THRESHOLD:
                status = "attention"
                movement = "decreased"
            else:
                status = "stable"
                movement = "remained broadly stable"
            message = (
                "Total sales remained broadly stable compared with the previous "
                "period."
                if status == "stable"
                else (
                    f"Total sales {movement} by "
                    f"{_format_percentage(abs(comparable_change))} compared with "
                    "the previous period."
                )
            )

        supporting_text = _sales_momentum_supporting_text(
            order_change,
            aov_change,
            current_sales.total_orders,
            previous_sales.total_orders,
        )
        return (
            SalesMomentumHighlight(
                id="sales_momentum",
                title="Sales Momentum",
                status=status,
                message=message,
                supporting_text=supporting_text,
                helper_text=(
                    f"Compares {filters.start_date.isoformat()} through "
                    f"{filters.end_date.isoformat()} with {previous_start.isoformat()} "
                    f"through {previous_end.isoformat()}."
                ),
                action_label="View daily performance",
                current_period=_comparison_period(
                    filters.start_date,
                    filters.end_date,
                    current_revenue,
                    current_sales.total_orders,
                ),
                previous_period=_comparison_period(
                    previous_start,
                    previous_end,
                    previous_revenue,
                    previous_sales.total_orders,
                ),
                total_sales_change_percentage=_optional_float(revenue_change),
                order_change=order_change,
                order_change_percentage=_optional_float(order_change_percentage),
                aov_change_percentage=_optional_float(aov_change),
            ),
            current_sales.currency_code or previous_sales.currency_code,
        )

    @staticmethod
    def _build_product_sales_concentration(result):
        if not result.top_products:
            return ProductSalesConcentrationHighlight(
                id="product_sales_concentration",
                title="Product Sales Concentration",
                status="unavailable",
                message=(
                    "Product sales concentration is unavailable because no "
                    "qualifying product sales were recorded."
                ),
                supporting_text=None,
                helper_text="Uses net product sales grouped by Shopify product ID.",
                action_label="View top products",
                top_product=None,
                products_in_top_group=0,
                top_group_net_product_sales=None,
                top_group_contribution_percentage=None,
                total_net_product_sales=None,
            )
        total = result.total_net_product_sales
        if total <= 0:
            return ProductSalesConcentrationHighlight(
                id="product_sales_concentration",
                title="Product Sales Concentration",
                status="unavailable",
                message=(
                    "Product sales concentration is unavailable because net "
                    "product sales were not positive during this period."
                ),
                supporting_text=None,
                helper_text="Uses net product sales grouped by Shopify product ID.",
                action_label="View top products",
                top_product=None,
                products_in_top_group=min(result.product_count, 3),
                top_group_net_product_sales=None,
                top_group_contribution_percentage=None,
                total_net_product_sales=float(_round_money(total)),
            )
        top_product = result.top_products[0]
        top_share = top_product.net_product_sales / total * Decimal("100")
        top_group_sales = sum(
            (product.net_product_sales for product in result.top_products),
            Decimal("0"),
        )
        top_group_share = top_group_sales / total * Decimal("100")
        if top_share >= HIGH_PRODUCT_CONCENTRATION_THRESHOLD:
            status = "high"
        elif top_share >= MODERATE_PRODUCT_CONCENTRATION_THRESHOLD:
            status = "moderate"
        else:
            status = "diversified"
        product_name = top_product.product_title or "Untitled product"
        group_count = len(result.top_products)
        supporting_text = (
            f"The {group_count} products sold generated all net product sales."
            if result.product_count < 3
            else (
                "The top three products contributed "
                f"{_format_percentage(top_group_share)} of net product sales."
            )
        )
        return ProductSalesConcentrationHighlight(
            id="product_sales_concentration",
            title="Product Sales Concentration",
            status=status,
            message=(
                f"{product_name} generated {_format_percentage(top_share)} of "
                "net product sales."
            ),
            supporting_text=supporting_text,
            helper_text=(
                "Order-level discounts and refunds are allocated in proportion "
                "to line-item gross sales."
            ),
            action_label="View top products",
            top_product=ProductConcentrationProduct(
                product_id=top_product.product_id,
                product_name=product_name,
                net_product_sales=float(_round_money(top_product.net_product_sales)),
                units_sold=top_product.units_sold,
                contribution_percentage=float(_round_percentage(top_share)),
            ),
            products_in_top_group=group_count,
            top_group_net_product_sales=float(_round_money(top_group_sales)),
            top_group_contribution_percentage=float(
                _round_percentage(top_group_share)
            ),
            total_net_product_sales=float(_round_money(total)),
        )

    @staticmethod
    def _build_inventory_exposure(result):
        helper_text = (
            "Based on sales in the selected period and current inventory levels."
        )
        if not result.inventory_available:
            return InventoryExposureHighlight(
                id="inventory_exposure",
                title="Inventory Exposure",
                status="unavailable",
                message="Current tracked inventory data is unavailable.",
                supporting_text=None,
                helper_text=helper_text,
                action_label="Review affected products",
                affected_product_count=0,
                low_stock_product_count=0,
                out_of_stock_product_count=0,
                affected_net_product_sales=None,
                affected_units_sold=None,
                highest_impact_product=None,
                inventory_as_of=None,
            )
        if result.affected_product_count == 0:
            return InventoryExposureHighlight(
                id="inventory_exposure",
                title="Inventory Exposure",
                status="healthy",
                message=(
                    "No recently selling products require inventory review for "
                    "this period."
                ),
                supporting_text=None,
                helper_text=helper_text,
                action_label="Review affected products",
                affected_product_count=0,
                low_stock_product_count=0,
                out_of_stock_product_count=0,
                affected_net_product_sales=0,
                affected_units_sold=0,
                highest_impact_product=None,
                inventory_as_of=(
                    result.inventory_as_of.isoformat()
                    if result.inventory_as_of
                    else None
                ),
            )
        status = (
            "critical" if result.out_of_stock_product_count else "warning"
        )
        top = result.highest_impact_product
        top_status = result.highest_impact_inventory_status
        highest_impact = None
        supporting_text = None
        if top is not None and top_status is not None:
            product_name = top.product_title or "Untitled product"
            status_label = top_status.replace("_", " ")
            supporting_text = (
                f"{product_name} has the highest exposure and is currently "
                f"{status_label}."
            )
            highest_impact = InventoryExposureProduct(
                product_id=top.product_id,
                product_name=product_name,
                inventory_status=top_status,
                net_product_sales=float(_round_money(top.net_product_sales)),
                units_sold=top.units_sold,
            )
        return InventoryExposureHighlight(
            id="inventory_exposure",
            title="Inventory Exposure",
            status=status,
            message=(
                f"{_format_count(result.affected_product_count, 'recently selling product')} "
                "currently need inventory attention. These products generated "
                f"{_format_money(result.affected_net_product_sales, result.currency_code)} "
                "in net product sales during the selected period."
            ),
            supporting_text=supporting_text,
            helper_text=helper_text,
            action_label="Review affected products",
            affected_product_count=result.affected_product_count,
            low_stock_product_count=result.low_stock_product_count,
            out_of_stock_product_count=result.out_of_stock_product_count,
            affected_net_product_sales=float(
                _round_money(result.affected_net_product_sales)
            ),
            affected_units_sold=result.affected_units_sold,
            highest_impact_product=highest_impact,
            inventory_as_of=(
                result.inventory_as_of.isoformat()
                if result.inventory_as_of
                else None
            ),
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
                self._action(
                    id="inventory_out_of_stock",
                    priority="critical",
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
                self._action(
                    id="inventory_low_stock",
                    priority="warning",
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
                self._action(
                    id="sales_no_orders",
                    priority="warning",
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
                    self._action(
                        id="sales_low_average_order_value",
                        priority="recommendation",
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

    def get_action_export(
        self,
        action_id: str,
        filters: OverviewFilters = OverviewFilters(),
    ) -> OverviewActionCsvExport:
        """Build the affected-record CSV for one supported overview action."""
        metadata = ACTION_METADATA.get(action_id)
        if metadata is None:
            raise LookupError(f"CSV export is not available for action '{action_id}'.")

        if action_id in {"inventory_out_of_stock", "inventory_low_stock"}:
            source_rows = self.repository.get_inventory_action_export_rows(
                action_id, self.low_stock_threshold, filters
            )
            records = [
                {
                    "product_id": self._csv_safe(row.product_id),
                    "affected_product_name": self._csv_safe(row.product_name),
                    "variant_title": self._csv_safe(row.variant_title),
                    "sku": self._csv_safe(row.sku),
                    "inventory_quantity": row.inventory_quantity,
                    "location_name": self._csv_safe(row.location_name),
                    "units_sold": row.units_sold,
                    "issue_type": action_id,
                    "issue_value": row.inventory_quantity,
                }
                for row in source_rows
            ]
        elif action_id == "sales_low_average_order_value":
            source_rows = self.repository.get_sales_action_export_rows(filters)
            records = [
                {
                    "order_id": self._csv_safe(row.order_id),
                    "product_name": self._csv_safe(row.product_name),
                    "units": row.units,
                    "gross_sales": self._decimal(row.gross_sales),
                    "discount_amount": self._decimal(row.discount_amount),
                    "net_sales": self._decimal(row.net_sales),
                    "issue_type": action_id,
                    "issue_value": self._decimal(self.low_aov_threshold),
                }
                for row in source_rows
            ]
        else:
            # A no-orders alert has no contributing order records by definition.
            records = []

        output = io.StringIO(newline="")
        writer = csv.DictWriter(
            output, fieldnames=metadata["columns"], lineterminator="\r\n"
        )
        writer.writeheader()
        writer.writerows(records)
        return OverviewActionCsvExport(
            filename=metadata["filename"],
            content=output.getvalue(),
        )

    @staticmethod
    def _action(*, id: str, **values) -> ActionNeededItem:
        metadata = ACTION_METADATA[id]
        return ActionNeededItem(
            id=id,
            category=metadata["category"],
            action_label=metadata["action_label"],
            action_url=metadata["action_url"],
            download_available=True,
            **values,
        )

    @staticmethod
    def _csv_safe(value: object | None) -> str:
        text = "" if value is None else str(value)
        if text.lstrip().startswith(("=", "+", "-", "@")):
            return f"'{text}"
        return text

    @staticmethod
    def _decimal(value: Decimal | None) -> str:
        return format(value, "f") if value is not None else ""


def _format_money(amount: Decimal, currency_code: str | None) -> str:
    formatted = f"{_round_money(amount):,.2f}"
    return f"{currency_code} {formatted}" if currency_code else formatted


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_percentage(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _format_percentage(amount: Decimal) -> str:
    return f"{_round_percentage(amount):.1f}%"


def _percentage_change(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return Decimal("0") if current == 0 else None
    return (current - previous) / previous * Decimal("100")


def _optional_float(value: Decimal | None) -> float | None:
    return float(_round_percentage(value)) if value is not None else None


def _comparison_period(
    start_date: date,
    end_date: date,
    total_sales: Decimal,
    orders: int,
) -> ComparisonPeriodMetrics:
    average_order_value = total_sales / orders if orders else Decimal("0")
    return ComparisonPeriodMetrics(
        start_date=start_date,
        end_date=end_date,
        total_sales=float(_round_money(total_sales)),
        orders=orders,
        average_order_value=float(_round_money(average_order_value)),
    )


def _sales_momentum_supporting_text(
    order_change: int,
    aov_change: Decimal | None,
    current_orders: int,
    previous_orders: int,
) -> str:
    if previous_orders == 0 and current_orders > 0:
        return (
            f"The store generated {_format_count(current_orders, 'order')} after "
            "recording no orders in the previous period."
        )
    if order_change > 0:
        order_text = f"Orders increased by {order_change:,}"
    elif order_change < 0:
        order_text = f"Orders decreased by {abs(order_change):,}"
    else:
        order_text = "Orders remained unchanged"
    if aov_change is None:
        aov_text = "average order value had no previous baseline"
    elif aov_change > 0:
        aov_text = f"average order value increased by {_format_percentage(aov_change)}"
    elif aov_change < 0:
        aov_text = (
            "average order value decreased by "
            f"{_format_percentage(abs(aov_change))}"
        )
    else:
        aov_text = "average order value remained unchanged"
    return f"{order_text}, while {aov_text}."


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
