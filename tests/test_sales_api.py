from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.sales_repository import (
    SalesActionExportRow,
    SalesFilterOptions,
    SalesFilters,
    SalesMetrics,
)
from app.routers.sales import (
    download_sales_action_needed_records,
    get_revenue_trend,
    get_sales_action_needed,
    get_sales_filter_options,
    get_sales_filters,
    get_sales_summary,
    router,
)
from app.schemas.sales import (
    RevenueTrendResponse,
    SalesActionNeededResponse,
    SalesFilterOptionsResponse,
)


class StubResult:
    def all(self):
        return [(date(2026, 1, 2), Decimal("125.75"), "USD")]


class StubSession:
    def execute(self, _statement):
        return StubResult()


class SalesApiTests(unittest.TestCase):
    def test_returns_chart_ready_response(self):
        response = get_revenue_trend(
            interval="daily",
            filters=SalesFilters(
                start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
            ),
            db=StubSession(),
        )

        self.assertEqual(
            response.model_dump(mode="json"),
            {
                "currency": "USD",
                "interval": "daily",
                "data": [{"date": "2026-01-02", "revenue": 125.75}],
                "highlights": {
                    "total_revenue": 125.75,
                    "highest_revenue_date": "2026-01-02",
                    "highest_daily_revenue": 125.75,
                },
            },
        )

    def test_route_uses_documented_path_and_response_model(self):
        route = next(
            route for route in router.routes if route.path == "/api/sales/revenue/trend"
        )

        self.assertEqual(route.response_model, RevenueTrendResponse)
        self.assertIn("GET", route.methods)

    def test_rejects_reversed_date_range(self):
        with self.assertRaises(HTTPException) as context:
            get_sales_filters(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 1, 1),
                sales_channel=None,
                financial_status=None,
                currency=None,
            )

        self.assertEqual(context.exception.status_code, 422)

    @patch("app.routers.sales.SalesRepository.get_sales_metrics")
    def test_sales_summary_contract_is_unchanged(self, get_metrics):
        get_metrics.return_value = SalesMetrics(
            gross_sales=Decimal("120.00"),
            discounts=Decimal("20.00"),
            net_sales=Decimal("100.00"),
            shipping=Decimal("5.00"),
            taxes=Decimal("10.00"),
            total_sales=Decimal("115.00"),
            orders_count=2,
            average_order_value=Decimal("57.50"),
            currency_code="USD",
            currency_count=1,
        )

        response = get_sales_summary(filters=SalesFilters(), db=object())

        self.assertEqual(response.model_dump(), {
            "gross_sales": 120.0,
            "discounts": 20.0,
            "net_sales": 100.0,
            "shipping": 5.0,
            "taxes": 10.0,
            "total_sales": 115.0,
            "orders_count": 2,
            "average_order_value": 57.5,
            "currency": "USD",
        })

    @patch("app.routers.sales.SalesRepository.get_filter_options")
    def test_filter_options_endpoint_returns_database_dimensions(self, get_options):
        get_options.return_value = SalesFilterOptions(
            sales_channels=("web",),
            financial_statuses=("PAID",),
            currency_codes=("USD",),
        )

        response = get_sales_filter_options(db=object())

        self.assertEqual(response.sales_channels[0].name, "Online Store")
        self.assertEqual(response.sales_channels[0].values, ["web"])
        self.assertEqual(response.order_statuses, ["PAID"])
        self.assertEqual(response.currencies, ["USD"])
        route = next(
            route for route in router.routes
            if route.path == "/api/sales/filter-options"
        )
        self.assertEqual(route.response_model, SalesFilterOptionsResponse)

    @patch("app.routers.sales.SalesRepository.get_sales_metrics")
    def test_action_needed_returns_clean_date_filtered_response(self, get_metrics):
        get_metrics.return_value = SalesMetrics(
            gross_sales=Decimal("100.00"),
            discounts=Decimal("25.00"),
            net_sales=Decimal("75.00"),
            shipping=Decimal("0.00"),
            taxes=Decimal("0.00"),
            total_sales=Decimal("40.00"),
            orders_count=2,
            average_order_value=Decimal("20.00"),
            currency_code="USD",
            currency_count=1,
        )

        response = get_sales_action_needed(
            filters=SalesFilters(
                start_date=date(2026, 8, 1),
                end_date=date(2026, 8, 10),
                sales_channels=("web",),
                financial_statuses=("PAID",),
                currency_codes=("USD",),
            ),
            db=object(),
            settings=SimpleNamespace(
                low_aov_threshold=Decimal("50.00"),
                high_discount_rate_threshold=Decimal("0.20"),
                refund_rate_threshold=Decimal("0.10"),
                cancellation_rate_threshold=Decimal("0.10"),
            ),
        )

        self.assertTrue(response.has_sufficient_data)
        self.assertEqual(
            [action.id for action in response.actions],
            ["sales_low_average_order_value", "sales_high_discount_usage"],
        )
        self.assertEqual(
            response.actions[0].model_dump(include={"action_label", "action_url"}),
            {
                "action_label": "Go to Products",
                "action_url": "shopify://admin/products",
            },
        )
        self.assertEqual(
            response.actions[1].model_dump(include={"action_label", "action_url"}),
            {
                "action_label": "Go to Discount",
                "action_url": "shopify://admin/discounts",
            },
        )
        called_filters = get_metrics.call_args.args[0]
        self.assertEqual(called_filters.sales_channels, ("web",))
        self.assertEqual(called_filters.financial_statuses, ("PAID",))
        self.assertEqual(called_filters.currency_codes, ("USD",))

    def test_action_needed_route_uses_documented_contract(self):
        route = next(
            route for route in router.routes
            if route.path == "/api/sales/action-needed"
        )

        self.assertEqual(route.response_model, SalesActionNeededResponse)
        self.assertIn("GET", route.methods)

    @patch("app.routers.sales.SalesRepository.get_action_export_rows")
    def test_action_export_returns_downloadable_csv(self, get_rows):
        get_rows.return_value = [
            SalesActionExportRow(
                order_id="gid://shopify/Order/1",
                product_name="Example product",
                financial_status="REFUNDED",
                amount_refunded=Decimal("10.00"),
                refund_reason="Customer request",
                cancelled_at=None,
                refunded_date=datetime(2026, 8, 9, tzinfo=timezone.utc),
            )
        ]

        response = download_sales_action_needed_records(
            action_id="sales_refund_cancellation_spike",
            filters=SalesFilters(
                start_date=date(2026, 8, 1), end_date=date(2026, 8, 10)
            ),
            db=object(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.media_type.startswith("text/csv"))
        self.assertIn("attachment;", response.headers["content-disposition"])
        self.assertIn(b"order_id,product_name,financial_status", response.body)
        self.assertIn(b"gid://shopify/Order/1,Example product", response.body)
        called_filters = get_rows.call_args.args[0]
        self.assertEqual(called_filters.start_date, date(2026, 8, 1))
        self.assertEqual(called_filters.end_date, date(2026, 8, 10))

    def test_action_export_route_is_reusable_and_rejects_unknown_actions(self):
        route = next(
            route for route in router.routes
            if route.path == "/api/sales/action-needed/{action_id}/download"
        )
        self.assertIn("GET", route.methods)

        with self.assertRaises(HTTPException) as context:
            download_sales_action_needed_records(
                action_id="unsupported",
                filters=SalesFilters(),
                db=object(),
            )
        self.assertEqual(context.exception.status_code, 404)

    @patch("app.routers.sales.SalesRepository.get_action_export_rows")
    def test_action_export_sanitizes_database_errors(self, get_rows):
        get_rows.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            download_sales_action_needed_records(
                action_id="sales_refund_cancellation_spike",
                filters=SalesFilters(),
                db=object(),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to export sales action needed records.",
        )
        self.assertNotIn("credentials", context.exception.detail)

    def test_action_needed_rejects_reversed_date_range(self):
        with self.assertRaises(HTTPException) as context:
            get_sales_filters(
                start_date=date(2026, 8, 10),
                end_date=date(2026, 8, 1),
                sales_channel=None,
                financial_status=None,
                currency=None,
            )

        self.assertEqual(context.exception.status_code, 422)

    @patch("app.routers.sales.SalesRepository.get_sales_metrics")
    def test_action_needed_sanitizes_database_errors(self, get_metrics):
        get_metrics.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_sales_action_needed(
                filters=SalesFilters(),
                db=object(),
                settings=SimpleNamespace(
                    low_aov_threshold=Decimal("50.00"),
                    high_discount_rate_threshold=Decimal("0.20"),
                    refund_rate_threshold=Decimal("0.10"),
                    cancellation_rate_threshold=Decimal("0.10"),
                ),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve sales action needed recommendations.",
        )
        self.assertNotIn("credentials", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
