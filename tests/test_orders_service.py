from datetime import date
import unittest

from app.repositories.orders_repository import OrderFilters, OrderKpiAggregate
from app.services.orders_service import OrdersService, build_order_filters


class StubOrdersRepository:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.received_filters = None

    def get_kpi_aggregates(self, filters):
        self.received_filters = filters
        return self.rows


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


if __name__ == "__main__":
    unittest.main()
