from datetime import date, datetime, timezone
from decimal import Decimal
import unittest

from app.repositories.orders_repository import (
    OrderChartDateBounds,
    OrderDimensionAggregate,
    OrderFilters,
    OrderKpiAggregate,
    OrderPeriodAggregate,
    OrderPerformanceResult,
    OrderPerformanceRow,
    OrderTimelineRow,
)
from app.services.orders_service import OrdersService, build_order_filters


class StubOrdersRepository:
    def __init__(
        self,
        rows=None,
        bounds=None,
        periods=None,
        channels=None,
        distribution=None,
        performance=None,
        timeline=None,
    ):
        self.rows = rows or []
        self.bounds = bounds or OrderChartDateBounds(None, None)
        self.periods = periods or []
        self.channels = channels or []
        self.distribution = distribution or []
        self.performance = performance or OrderPerformanceResult([], 0)
        self.timeline = timeline
        self.received_filters = None
        self.received_granularity = None
        self.performance_args = None

    def get_kpi_aggregates(self, filters):
        self.received_filters = filters
        return self.rows

    def get_chart_date_bounds(self, filters):
        self.received_filters = filters
        return self.bounds

    def get_period_aggregates(self, filters, granularity):
        self.received_filters = filters
        self.received_granularity = granularity
        return self.periods

    def get_sales_channel_aggregates(self, filters):
        self.received_filters = filters
        return self.channels

    def get_status_distribution(self, filters):
        self.received_filters = filters
        return self.distribution

    def get_performance_insights(self, *args):
        self.performance_args = args
        return self.performance

    def get_timeline(self, order_id):
        self.received_order_id = order_id
        return self.timeline


class OrdersServiceTests(unittest.TestCase):
    def test_build_filters_validates_dates_and_deduplicates_channels(self):
        filters = build_order_filters(
            date(2026, 8, 1),
            date(2026, 8, 17),
            ["web", "web", "pos"],
            ["Open", "open"],
            ["FULFILLED", "FULFILLED"],
            ["PAID", "PAID"],
        )
        self.assertEqual(filters.sales_channels, ("web", "pos"))
        self.assertEqual(filters.order_statuses, ("open",))
        self.assertEqual(filters.fulfillment_statuses, ("FULFILLED",))
        self.assertEqual(filters.payment_statuses, ("PAID",))

        with self.assertRaisesRegex(ValueError, "start_date"):
            build_order_filters(date(2026, 8, 18), date(2026, 8, 17))

        with self.assertRaisesRegex(ValueError, "Unsupported order_status"):
            build_order_filters(None, None, order_statuses=["archived"])

    def test_kpis_normalize_statuses_and_calculate_fulfillment_rate(self):
        repository = StubOrdersRepository(
            [
                OrderKpiAggregate("FULFILLED", 7, 12, 1, 1),
                OrderKpiAggregate("partially fulfilled", 1, 3, 0, 1),
                OrderKpiAggregate("unfulfilled", 2, 5, 0, 0),
                OrderKpiAggregate("ON_HOLD", 1, 1, 0, 0),
            ]
        )
        filters = OrderFilters(sales_channels=("web",))

        response = OrdersService(repository).get_kpis(filters)

        self.assertEqual(repository.received_filters, filters)
        self.assertEqual(
            response.model_dump(),
            {
                "total_orders": 11,
                "units_ordered": 21,
                "unfulfilled_orders": 2,
                "partially_fulfilled_orders": 1,
                "fulfilled_orders": 7,
                "cancelled_orders": 1,
                "refunded_orders": 2,
                "fulfillment_rate": 70.0,
            },
        )

    def test_empty_result_returns_safe_zero_values(self):
        response = OrdersService(StubOrdersRepository()).get_kpis()

        self.assertEqual(
            response.model_dump(),
            {
                "total_orders": 0,
                "units_ordered": 0,
                "unfulfilled_orders": 0,
                "partially_fulfilled_orders": 0,
                "fulfilled_orders": 0,
                "cancelled_orders": 0,
                "refunded_orders": 0,
                "fulfillment_rate": 0.0,
            },
        )

    def test_charts_fill_missing_dates_and_reuse_fulfillment_rules(self):
        repository = StubOrdersRepository(
            rows=[
                OrderKpiAggregate("fulfilled", 4, 8, 0, 0),
                OrderKpiAggregate("UNFULFILLED", 2, 3, 0, 0),
                OrderKpiAggregate("partially fulfilled", 1, 1, 0, 0),
            ],
            bounds=OrderChartDateBounds(date(2026, 8, 3), date(2026, 8, 18)),
            periods=[
                OrderPeriodAggregate(date(2026, 8, 3), 5, 1, 2),
                OrderPeriodAggregate(date(2026, 8, 17), 2, 0, 1),
            ],
            channels=[
                OrderDimensionAggregate("web", 4),
                OrderDimensionAggregate("mobile_app", 2),
                OrderDimensionAggregate(None, 1),
            ],
            distribution=[
                OrderDimensionAggregate("Fulfilled", 3),
                OrderDimensionAggregate("Unfulfilled", 2),
                OrderDimensionAggregate("Cancelled", 1),
                OrderDimensionAggregate("Refunded", 1),
            ],
        )
        filters = OrderFilters(start_date=date(2026, 8, 3), end_date=date(2026, 8, 18))

        response = OrdersService(repository).get_charts(filters)

        self.assertEqual(repository.received_granularity, "week")
        self.assertEqual(
            [(point.date, point.orders) for point in response.orders_trend],
            [
                (date(2026, 8, 3), 5),
                (date(2026, 8, 10), 0),
                (date(2026, 8, 17), 2),
            ],
        )
        self.assertEqual(
            [(point.status, point.orders) for point in response.fulfillment_status],
            [("Fulfilled", 4), ("Unfulfilled", 2), ("Partially Fulfilled", 1)],
        )
        self.assertEqual(
            [(point.sales_channel, point.orders) for point in response.orders_by_sales_channel],
            [
                ("Online Store", 4),
                ("Other/app-specific channels", 2),
                ("Unknown", 1),
            ],
        )
        self.assertEqual(response.order_exceptions_trend[1].cancelled_orders, 0)
        self.assertEqual(response.order_exceptions_trend[1].refunded_orders, 0)
        self.assertEqual(
            [(point.status, point.orders) for point in response.order_status_distribution],
            [
                ("Fulfilled", 3),
                ("Unfulfilled", 2),
                ("Cancelled", 1),
                ("Refunded", 1),
            ],
        )

    def test_chart_granularity_is_always_weekly(self):
        self.assertEqual(
            OrdersService._chart_granularity(date(2026, 1, 1), date(2026, 1, 31)),
            "week",
        )
        self.assertEqual(
            OrdersService._chart_granularity(date(2026, 1, 1), date(2026, 2, 1)),
            "week",
        )
        self.assertEqual(
            OrdersService._chart_granularity(date(2026, 1, 1), date(2026, 6, 30)),
            "week",
        )

    def test_week_and_month_period_filling_aligns_period_starts(self):
        weekly = OrdersService._fill_periods(
            [], date(2026, 8, 5), date(2026, 8, 18), "week"
        )
        monthly = OrdersService._fill_periods(
            [], date(2026, 1, 31), date(2026, 3, 1), "month"
        )

        self.assertEqual(
            [row.date for row in weekly],
            [date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 17)],
        )
        self.assertEqual(
            [row.date for row in monthly],
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
        )

    def test_fulfillment_details_normalize_status_progress_and_health(self):
        repository = StubOrdersRepository(
            performance=OrderPerformanceResult(
                rows=[
                    OrderPerformanceRow(
                        "gid://shopify/Order/101",
                        "#101",
                        datetime(2026, 8, 1, tzinfo=timezone.utc),
                        "FULFILLED",
                        None,
                        3,
                    ),
                    OrderPerformanceRow(
                        "gid://shopify/Order/102",
                        "#102",
                        datetime(2026, 8, 2, tzinfo=timezone.utc),
                        "PARTIALLY_FULFILLED",
                        None,
                        2,
                    ),
                ],
                total_items=2,
            )
        )

        response = OrdersService(repository).get_performance_insights(
            OrderFilters(),
            1,
            10,
            "  #10  ",
            "order_date",
            "desc",
            datetime(2026, 8, 3, tzinfo=timezone.utc),
        )

        self.assertEqual(response.pagination.total_pages, 1)
        self.assertEqual(repository.performance_args[3], "#10")
        first, second = response.items
        self.assertEqual(first.fulfillment_status, "fulfilled")
        self.assertEqual(first.fulfillment_health, "healthy")
        self.assertIsNone(first.fulfillment_health_reason)
        self.assertEqual(first.order_progress, "fulfilled")
        self.assertEqual(first.order_progress_label, "Fulfilled")
        self.assertIsNone(first.order_progress_seconds)
        self.assertEqual(first.shopify_admin_url, "shopify://admin/orders/101")
        self.assertEqual(second.fulfillment_status, "partially_fulfilled")
        self.assertEqual(second.fulfillment_health, "attention_needed")
        self.assertEqual(
            second.fulfillment_health_reason, "Order is partially fulfilled"
        )
        self.assertEqual(second.order_progress, "in_progress")
        self.assertEqual(second.order_progress_label, "In progress for 1 day")

    def test_cancelled_fulfillment_health_has_precedence(self):
        row = OrderPerformanceRow(
            "gid://shopify/Order/103",
            None,
            datetime(2026, 8, 3, tzinfo=timezone.utc),
            "UNFULFILLED",
            datetime(2026, 8, 4, tzinfo=timezone.utc),
            0,
        )
        repository = StubOrdersRepository(
            performance=OrderPerformanceResult([row], 1)
        )

        item = OrdersService(repository).get_performance_insights(
            OrderFilters(),
            1,
            10,
            "",
            "fulfillment_health",
            "desc",
            datetime(2026, 8, 10, tzinfo=timezone.utc),
        ).items[0]

        self.assertEqual(item.fulfillment_status, "cancelled")
        self.assertEqual(item.fulfillment_health, "cancelled")
        self.assertEqual(item.order_name, "Order 103")
        self.assertEqual(item.fulfillment_health_reason, "Order is cancelled")
        self.assertEqual(item.order_progress_label, "Cancelled")
        self.assertIsNone(item.order_progress_seconds)

    def test_order_progress_age_affects_only_current_open_orders(self):
        current_time = datetime(2026, 8, 10, tzinfo=timezone.utc)
        rows = [
            OrderPerformanceRow(
                f"gid://shopify/Order/{identifier}",
                f"#{identifier}",
                processed_at,
                status,
                None,
                1,
            )
            for identifier, processed_at, status in [
                (201, datetime(2026, 8, 7, tzinfo=timezone.utc), "UNFULFILLED"),
                (202, datetime(2026, 8, 3, tzinfo=timezone.utc), "PARTIAL"),
                (203, datetime(2026, 1, 1, tzinfo=timezone.utc), "FULFILLED"),
                (204, datetime(2026, 8, 1, tzinfo=timezone.utc), None),
            ]
        ]
        repository = StubOrdersRepository(
            performance=OrderPerformanceResult(rows, 4)
        )

        items = OrdersService(repository).get_performance_insights(
            OrderFilters(),
            1,
            10,
            "",
            "order_progress",
            "desc",
            current_time,
        ).items

        self.assertEqual(items[0].order_progress_label, "Open for 3 days")
        self.assertEqual(items[0].fulfillment_health, "attention_needed")
        self.assertEqual(
            items[0].fulfillment_health_reason,
            "Unfulfilled for more than 2 days",
        )
        self.assertEqual(items[1].order_progress_label, "In progress for 7 days")
        self.assertEqual(items[1].fulfillment_health, "critical")
        self.assertEqual(
            items[1].fulfillment_health_reason,
            "Partially fulfilled for more than 5 days",
        )
        self.assertEqual(items[2].order_progress_label, "Fulfilled")
        self.assertEqual(items[2].fulfillment_health, "healthy")
        self.assertEqual(items[3].order_progress_label, "Unknown")
        self.assertEqual(items[3].fulfillment_health, "unknown")
        self.assertIsNone(items[3].order_progress_seconds)

    def test_timeline_uses_only_reliable_timestamps_and_sorts_events(self):
        repository = StubOrdersRepository(
            timeline=OrderTimelineRow(
                "gid://shopify/Order/301",
                "#301",
                datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 8, 1, 9, 5, tzinfo=timezone.utc),
                datetime(2026, 8, 3, 11, 0, tzinfo=timezone.utc),
                datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
                Decimal("25.50"),
                "Damaged item",
                "PARTIALLY_REFUNDED",
                "FULFILLED",
                "USD",
            )
        )

        response = OrdersService(repository).get_timeline(
            "gid://shopify/Order/301"
        )

        self.assertEqual(repository.received_order_id, "gid://shopify/Order/301")
        self.assertEqual(
            [event.event_type for event in response.events],
            [
                "order_created",
                "order_processed",
                "refund_recorded",
                "order_cancelled",
            ],
        )
        self.assertEqual(response.events[2].amount, 25.5)
        self.assertEqual(response.events[2].description, "Damaged item")
        self.assertEqual(response.current_status.fulfillment_status, "fulfilled")
        self.assertFalse(
            response.current_status.fulfillment_timestamp_available
        )

    def test_timeline_does_not_fabricate_missing_events(self):
        repository = StubOrdersRepository(
            timeline=OrderTimelineRow(
                "gid://shopify/Order/302",
                None,
                None,
                None,
                None,
                None,
                Decimal("0"),
                None,
                None,
                "FULFILLED",
                None,
            )
        )

        response = OrdersService(repository).get_timeline(
            "gid://shopify/Order/302"
        )

        self.assertEqual(response.events, [])
        self.assertEqual(response.order_name, "Order 302")
        self.assertEqual(response.current_status.fulfillment_status, "fulfilled")
        with self.assertRaisesRegex(ValueError, "Invalid Shopify order ID"):
            OrdersService(repository).get_timeline("301")


if __name__ == "__main__":
    unittest.main()
