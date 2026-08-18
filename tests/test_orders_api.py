from datetime import date
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.orders_repository import OrderFilters, OrderKpiAggregate
from app.main import app
from app.routers.orders import (
    get_order_charts,
    get_order_filters,
    get_order_kpis,
    get_order_performance_insights,
    get_order_timeline,
    router,
)
from app.schemas.orders import (
    OrderChartsResponse,
    OrderKpiResponse,
    OrderPerformanceResponse,
    OrderTimelineResponse,
)


class OrdersApiTests(unittest.TestCase):
    def test_route_uses_single_documented_endpoint_and_response_model(self):
        route = next(route for route in router.routes if route.path == "/api/orders/kpis")

        self.assertEqual(route.response_model, OrderKpiResponse)
        self.assertIn("GET", route.methods)
        self.assertEqual(len(router.routes), 4)
        self.assertIn("/api/orders/kpis", app.openapi()["paths"])

        chart_route = next(
            route for route in router.routes if route.path == "/api/orders/charts"
        )
        self.assertEqual(chart_route.response_model, OrderChartsResponse)
        self.assertIn("GET", chart_route.methods)
        self.assertIn("/api/orders/charts", app.openapi()["paths"])

        performance_route = next(
            route
            for route in router.routes
            if route.path == "/api/orders/performance-insights"
        )
        self.assertEqual(performance_route.response_model, OrderPerformanceResponse)
        self.assertIn("GET", performance_route.methods)
        self.assertIn("/api/orders/performance-insights", app.openapi()["paths"])
        timeline_route = next(
            route for route in router.routes if route.name == "get_order_timeline"
        )
        self.assertEqual(timeline_route.response_model, OrderTimelineResponse)
        self.assertIn("GET", timeline_route.methods)
        self.assertIn(
            "/api/orders/{order_id}/timeline", app.openapi()["paths"]
        )

    @patch("app.routers.orders.OrdersRepository.get_kpi_aggregates")
    def test_endpoint_returns_clean_filtered_response(self, get_aggregates):
        get_aggregates.return_value = [
            OrderKpiAggregate("FULFILLED", 3, 8, 0, 1),
            OrderKpiAggregate("UNFULFILLED", 1, 2, 0, 0),
        ]
        filters = OrderFilters(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 17),
            sales_channels=("web",),
        )

        response = get_order_kpis(filters=filters, db=object())

        self.assertEqual(response.total_orders, 4)
        self.assertEqual(response.units_ordered, 10)
        self.assertEqual(response.fulfillment_rate, 75.0)
        self.assertEqual(get_aggregates.call_args.args[0], filters)

    def test_filter_dependency_rejects_reversed_dates(self):
        with self.assertRaises(HTTPException) as context:
            get_order_filters(
                start_date=date(2026, 8, 18),
                end_date=date(2026, 8, 17),
                sales_channel=None,
                order_status=None,
                fulfillment_status=None,
                payment_status=None,
            )

        self.assertEqual(context.exception.status_code, 422)

    def test_filter_dependency_maps_the_three_status_groups(self):
        filters = get_order_filters(
            start_date=None,
            end_date=None,
            sales_channel=["web"],
            order_status=["open"],
            fulfillment_status=["FULFILLED"],
            payment_status=["PAID"],
        )

        self.assertEqual(filters.order_statuses, ("open",))
        self.assertEqual(filters.fulfillment_statuses, ("FULFILLED",))
        self.assertEqual(filters.payment_statuses, ("PAID",))

    @patch("app.routers.orders.OrdersRepository.get_kpi_aggregates")
    def test_endpoint_sanitizes_database_errors(self, get_aggregates):
        get_aggregates.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_order_kpis(filters=OrderFilters(), db=object())

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.detail, "Unable to retrieve order KPI data.")
        self.assertNotIn("credentials", context.exception.detail)

    @patch("app.routers.orders.OrdersRepository.get_chart_date_bounds")
    def test_chart_endpoint_sanitizes_database_errors(self, get_bounds):
        get_bounds.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_order_charts(filters=OrderFilters(), db=object())

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.detail, "Unable to retrieve order chart data.")
        self.assertNotIn("credentials", context.exception.detail)

    @patch("app.routers.orders.OrdersRepository.get_performance_insights")
    def test_performance_endpoint_sanitizes_database_errors(self, get_performance):
        get_performance.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_order_performance_insights(
                page=1,
                page_size=25,
                search="",
                sort_by="order_date",
                sort_direction="desc",
                filters=OrderFilters(),
                db=object(),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve order fulfillment detail data.",
        )
        self.assertNotIn("credentials", context.exception.detail)

    @patch("app.routers.orders.OrdersRepository.get_timeline")
    def test_timeline_endpoint_handles_invalid_missing_and_database_errors(
        self, get_timeline
    ):
        with self.assertRaises(HTTPException) as invalid:
            get_order_timeline(order_id="301", db=object())
        self.assertEqual(invalid.exception.status_code, 422)

        get_timeline.return_value = None
        with self.assertRaises(HTTPException) as missing:
            get_order_timeline(
                order_id="gid://shopify/Order/301", db=object()
            )
        self.assertEqual(missing.exception.status_code, 404)

        get_timeline.side_effect = SQLAlchemyError("database credentials")
        with self.assertRaises(HTTPException) as failed:
            get_order_timeline(
                order_id="gid://shopify/Order/301", db=object()
            )
        self.assertEqual(failed.exception.status_code, 500)
        self.assertNotIn("credentials", failed.exception.detail)


if __name__ == "__main__":
    unittest.main()
