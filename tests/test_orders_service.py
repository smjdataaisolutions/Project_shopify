from datetime import date
import unittest

from app.repositories.orders_repository import (
    OrderChartDateBounds,
    OrderDimensionAggregate,
    OrderFilters,
    OrderKpiAggregate,
    OrderPeriodAggregate,
)
from app.services.orders_service import OrdersService, build_order_filters


class StubOrdersRepository:
    def __init__(
        self, rows=None, bounds=None, periods=None, channels=None, distribution=None
    ):
        self.rows = rows or []
        self.bounds = bounds or OrderChartDateBounds(None, None)
        self.periods = periods or []
        self.channels = channels or []
        self.distribution = distribution or []
        self.received_filters = None
        self.received_granularity = None

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


if __name__ == "__main__":
    unittest.main()
