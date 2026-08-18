import os
import unittest
from sqlalchemy import select

from app.db.models import Order
from app.db.session import SessionLocal
from app.repositories.orders_repository import OrderFilters, OrdersRepository
from app.services.orders_service import OrdersService


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class OrdersKpiPostgresTests(unittest.TestCase):
    def test_configured_postgresql_returns_valid_order_kpis(self):
        with SessionLocal() as db:
            response = OrdersService(OrdersRepository(db)).get_kpis()

        self.assertGreaterEqual(response.total_orders, 0)
        self.assertGreaterEqual(response.units_ordered, 0)
        self.assertGreaterEqual(response.cancelled_orders, 0)
        self.assertGreaterEqual(response.refunded_orders, 0)
        self.assertGreaterEqual(response.fulfillment_rate, 0.0)

    def test_configured_postgresql_returns_reconciling_order_charts(self):
        with SessionLocal() as db:
            service = OrdersService(OrdersRepository(db))
            kpis = service.get_kpis()
            charts = service.get_charts()

        fulfillment = {point.status: point.orders for point in charts.fulfillment_status}
        self.assertEqual(fulfillment["Fulfilled"], kpis.fulfilled_orders)
        self.assertEqual(fulfillment["Unfulfilled"], kpis.unfulfilled_orders)
        self.assertEqual(
            fulfillment["Partially Fulfilled"], kpis.partially_fulfilled_orders
        )
        self.assertEqual(
            sum(point.orders for point in charts.orders_by_sales_channel),
            kpis.total_orders,
        )
        self.assertEqual(
            sum(point.orders for point in charts.order_status_distribution),
            kpis.total_orders,
        )

    def test_configured_postgresql_returns_distinct_performance_rows(self):
        with SessionLocal() as db:
            response = OrdersService(OrdersRepository(db)).get_performance_insights(
                filters=OrderFilters(),
                page=1,
                page_size=100,
                search="",
                sort_by="order_date",
                sort_direction="desc",
            )

        order_ids = [item.order_id for item in response.items]
        self.assertEqual(len(order_ids), len(set(order_ids)))
        self.assertGreaterEqual(response.pagination.total_items, len(order_ids))
        self.assertEqual(response.meta.order_grain, "one_order")
        self.assertFalse(response.meta.historical_fulfillment_time_supported)
        self.assertTrue(response.meta.order_progress_age_supported)
        self.assertFalse(response.meta.not_required_supported)

    def test_configured_postgresql_returns_reliable_order_timeline(self):
        with SessionLocal() as db:
            order_id = db.scalar(select(Order.id).limit(1))
            response = (
                OrdersService(OrdersRepository(db)).get_timeline(order_id)
                if order_id
                else None
            )

        if order_id:
            self.assertIsNotNone(response)
            self.assertEqual(response.order_id, order_id)
            self.assertEqual(
                response.events,
                sorted(response.events, key=lambda event: event.occurred_at),
            )
            self.assertFalse(
                response.current_status.fulfillment_timestamp_available
            )



if __name__ == "__main__":
    unittest.main()
