import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import io

from app.repositories.sales_repository import (
    SalesActionExportRow,
    SalesFilters,
    SalesMetrics,
    SalesRepository,
)
from app.schemas.sales import (
    RevenueTrendHighlights,
    RevenueTrendPoint,
    RevenueTrendResponse,
    SalesAction,
    SalesActionNeededResponse,
    SalesChannelFilterOption,
    SalesFilterOptionsResponse,
    SalesSummary,
)
from app.services.sales_channel_service import group_sales_channels


REFUND_CANCELLATION_ACTION_ID = "sales_refund_cancellation_spike"
CSV_COLUMNS = (
    "order_id",
    "product_name",
    "financial_status",
    "amount_refunded",
    "refund_reason",
    "cancelled_at",
    "refunded_date",
)


@dataclass(frozen=True)
class SalesActionCsvExport:
    filename: str
    content: str


def build_sales_filters(
    start_date: date | None,
    end_date: date | None,
    sales_channels: list[str] | None = None,
    financial_statuses: list[str] | None = None,
    currency_codes: list[str] | None = None,
) -> SalesFilters:
    SalesService._validate_date_range(start_date, end_date)
    return SalesFilters(
        start_date=start_date,
        end_date=end_date,
        sales_channels=tuple(dict.fromkeys(sales_channels or [])),
        financial_statuses=tuple(dict.fromkeys(financial_statuses or [])),
        currency_codes=tuple(dict.fromkeys(currency_codes or [])),
    )


class SalesService:
    """Business logic for sales analytics."""

    def __init__(
        self,
        repository: SalesRepository,
        low_aov_threshold: Decimal = Decimal("50.00"),
        high_discount_rate_threshold: Decimal = Decimal("0.20"),
        refund_rate_threshold: Decimal = Decimal("0.10"),
        cancellation_rate_threshold: Decimal = Decimal("0.10"),
    ) -> None:
        self.repository = repository
        self.low_aov_threshold = low_aov_threshold
        self.high_discount_rate_threshold = high_discount_rate_threshold
        self.refund_rate_threshold = refund_rate_threshold
        self.cancellation_rate_threshold = cancellation_rate_threshold

    def get_sales_summary(self, filters: SalesFilters = SalesFilters()) -> SalesSummary:
        metrics = self.repository.get_sales_metrics(filters)
        return SalesSummary(
            gross_sales=float(metrics.gross_sales or 0),
            discounts=float(metrics.discounts or 0),
            net_sales=float(metrics.net_sales or 0),
            shipping=float(metrics.shipping or 0),
            taxes=float(metrics.taxes or 0),
            total_sales=float(metrics.total_sales or 0),
            orders_count=metrics.orders_count or 0,
            average_order_value=float(metrics.average_order_value or 0),
            currency=(
                metrics.currency_code
                if metrics.currency_count == 1 and metrics.currency_code
                else None
            ),
        )

    def get_filter_options(self) -> SalesFilterOptionsResponse:
        options = self.repository.get_filter_options()
        return SalesFilterOptionsResponse(
            sales_channels=[
                SalesChannelFilterOption(id=category_id, name=name, values=values)
                for category_id, name, values in group_sales_channels(
                    options.sales_channels
                )
            ],
            order_statuses=list(options.financial_statuses),
            currencies=list(options.currency_codes),
        )

    def get_revenue_trend(
        self,
        filters: SalesFilters,
    ) -> RevenueTrendResponse:
        rows = self.repository.get_revenue_trend(filters)
        points = [
            RevenueTrendPoint(date=period, revenue=float(revenue))
            for period, revenue, _currency in rows
        ]
        currency = next(
            (currency for _period, _revenue, currency in rows if currency), None
        )

        highlights = None
        if points:
            highest_period, highest_revenue, _currency = max(
                rows, key=lambda row: row[1]
            )
            highlights = RevenueTrendHighlights(
                total_revenue=float(
                    sum((revenue for _period, revenue, _currency in rows), Decimal(0))
                ),
                highest_revenue_date=highest_period,
                highest_daily_revenue=float(highest_revenue),
            )

        return RevenueTrendResponse(
            currency=currency,
            interval="daily",
            data=points,
            highlights=highlights,
        )

    def get_action_needed(
        self,
        filters: SalesFilters,
    ) -> SalesActionNeededResponse:
        metrics = self.repository.get_sales_metrics(filters)
        actions: list[SalesAction] = []

        if metrics.orders_count == 0:
            actions.append(
                SalesAction(
                    id="sales_no_orders",
                    priority="warning",
                    category="sales",
                    title="No orders in the selected period",
                    message="No orders were recorded during the selected period.",
                    recommended_action=(
                        "Review store traffic, product visibility, and current "
                        "marketing activity."
                    ),
                    action_label="Go to Orders",
                    action_url="shopify://admin/orders",
                )
            )
        elif metrics.orders_count is not None and metrics.orders_count > 0:
            rate_messages = []
            if metrics.refunded_orders is not None:
                refund_rate = Decimal(metrics.refunded_orders) / metrics.orders_count
                if refund_rate > self.refund_rate_threshold:
                    rate_messages.append(
                        "Refunded orders represent "
                        f"{self._format_percentage(refund_rate)} of orders"
                    )
            if metrics.cancelled_orders is not None:
                cancellation_rate = (
                    Decimal(metrics.cancelled_orders) / metrics.orders_count
                )
                if cancellation_rate > self.cancellation_rate_threshold:
                    rate_messages.append(
                        "cancelled orders represent "
                        f"{self._format_percentage(cancellation_rate)} of orders"
                    )
            if rate_messages:
                message = " and ".join(rate_messages)
                actions.append(
                    SalesAction(
                        id="sales_refund_cancellation_spike",
                        priority="warning",
                        category="sales",
                        title="Refund or cancellation rate is high",
                        message=f"{message[0].upper()}{message[1:]}.",
                        recommended_action=(
                            "Review refund reasons, cancellation causes, product "
                            "expectations, fulfillment issues, and payment problems."
                        ),
                        action_label="Go to Orders",
                        action_url="shopify://admin/orders",
                        download_available=True,
                    )
                )

            if (
                metrics.average_order_value is not None
                and metrics.average_order_value < self.low_aov_threshold
            ):
                actions.append(
                    SalesAction(
                        id="sales_low_average_order_value",
                        priority="recommendation",
                        category="sales",
                        title="Average order value can be improved",
                        message=(
                            "Average order value is "
                            f"{self._format_money(metrics.average_order_value, metrics)}."
                        ),
                        recommended_action=(
                            "Consider product bundles, cross-sells, upsells, or a "
                            "free-shipping threshold to increase order value."
                        ),
                        action_label="Go to Products",
                        action_url="shopify://admin/products",
                    )
                )

        if (
            metrics.gross_sales is not None
            and metrics.discounts is not None
            and metrics.gross_sales > 0
        ):
            discount_rate = metrics.discounts / metrics.gross_sales
            if discount_rate > self.high_discount_rate_threshold:
                actions.append(
                    SalesAction(
                        id="sales_high_discount_usage",
                        priority="recommendation",
                        category="sales",
                        title="Discount usage is high",
                        message=(
                            "Discounts represent "
                            f"{self._format_percentage(discount_rate)} of gross sales."
                        ),
                        recommended_action=(
                            "Review your discount strategy to ensure promotions are "
                            "supporting profitable sales."
                        ),
                        action_label="Go to Discount",
                        action_url="shopify://admin/discounts",
                    )
                )

        priority_order = {"critical": 0, "warning": 1, "recommendation": 2}
        rule_order = {
            "sales_no_orders": 0,
            "sales_refund_cancellation_spike": 1,
            "sales_low_average_order_value": 2,
            "sales_high_discount_usage": 3,
        }
        unique_actions = {action.id: action for action in actions}
        ordered_actions = sorted(
            unique_actions.values(),
            key=lambda action: (priority_order[action.priority], rule_order[action.id]),
        )[:5]
        has_sufficient_data = metrics.orders_count is not None and (
            metrics.orders_count == 0
            or (
                metrics.average_order_value is not None
                and metrics.gross_sales is not None
                and metrics.discounts is not None
                and metrics.refunded_orders is not None
                and metrics.cancelled_orders is not None
            )
        )
        return SalesActionNeededResponse(
            has_sufficient_data=has_sufficient_data,
            actions=ordered_actions,
        )

    def get_action_export(
        self,
        action_id: str,
        filters: SalesFilters,
    ) -> SalesActionCsvExport:
        """Build a safe CSV export for a supported Sales Action Needed rule."""
        if action_id != REFUND_CANCELLATION_ACTION_ID:
            raise LookupError(f"CSV export is not available for action '{action_id}'.")

        rows = self.repository.get_action_export_rows(filters)
        records = self._group_action_export_rows(rows)
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(records)
        return SalesActionCsvExport(
            filename="sales-refund-cancellation-records.csv",
            content=output.getvalue(),
        )

    @classmethod
    def _group_action_export_rows(
        cls,
        rows: list[SalesActionExportRow],
    ) -> list[dict[str, str]]:
        grouped: dict[str, dict] = {}
        for row in rows:
            record = grouped.setdefault(
                row.order_id,
                {
                    "row": row,
                    "product_names": set(),
                },
            )
            if row.product_name:
                record["product_names"].add(row.product_name)

        records = []
        for order_id, grouped_record in grouped.items():
            row = grouped_record["row"]
            product_names = " | ".join(sorted(grouped_record["product_names"]))
            records.append({
                "order_id": cls._csv_safe(order_id),
                "product_name": cls._csv_safe(product_names),
                "financial_status": cls._csv_safe(row.financial_status),
                "amount_refunded": (
                    format(row.amount_refunded, "f")
                    if row.amount_refunded is not None
                    else ""
                ),
                "refund_reason": cls._csv_safe(row.refund_reason),
                "cancelled_at": (
                    row.cancelled_at.isoformat() if row.cancelled_at else ""
                ),
                "refunded_date": (
                    row.refunded_date.isoformat() if row.refunded_date else ""
                ),
            })
        return records

    @staticmethod
    def _csv_safe(value: object | None) -> str:
        text = "" if value is None else str(value)
        if text.lstrip().startswith(("=", "+", "-", "@")):
            return f"'{text}"
        return text

    @staticmethod
    def _validate_date_range(
        start_date: date | None,
        end_date: date | None,
    ) -> None:
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")

    @staticmethod
    def _format_money(value: Decimal, metrics: SalesMetrics) -> str:
        amount = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        currency = (
            f"{metrics.currency_code} "
            if metrics.currency_count == 1 and metrics.currency_code
            else ""
        )
        return f"{currency}{amount:,.2f}"

    @staticmethod
    def _format_percentage(rate: Decimal) -> str:
        percentage = (rate * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        formatted = f"{percentage:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}%"
