import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import io
import unittest

from app.repositories.sales_repository import (
    SalesActionExportRow,
    SalesFilterOptions,
    SalesFilters,
    SalesMetrics,
)
from app.services.sales_service import SalesService, build_sales_filters


class StubSalesRepository:
    def __init__(self, rows=(), metrics=None):
        self.rows = list(rows)
        self.metrics = metrics
        self.received_dates = None

    def get_revenue_trend(self, filters):
        self.received_dates = (filters.start_date, filters.end_date)
        return self.rows

    def get_sales_metrics(self, filters=SalesFilters()):
        self.received_dates = (filters.start_date, filters.end_date)
        return self.metrics

    def get_action_export_rows(self, filters):
        self.received_dates = (filters.start_date, filters.end_date)
        return self.rows

    def get_filter_options(self):
        return SalesFilterOptions(
            sales_channels=("web", "pos", "mobile_app"),
            financial_statuses=("PAID", "REFUNDED"),
            currency_codes=("CAD", "USD"),
        )


def build_metrics(
    *,
    gross_sales=Decimal("100.00"),
    discounts=Decimal("0.00"),
    net_sales=None,
    total_sales=Decimal("100.00"),
    orders_count=2,
    average_order_value=Decimal("50.00"),
    currency_code="USD",
    currency_count=1,
    refunded_orders=0,
    cancelled_orders=0,
):
    return SalesMetrics(
        gross_sales=gross_sales,
        discounts=discounts,
        net_sales=total_sales if net_sales is None else net_sales,
        shipping=Decimal("0.00"),
        taxes=Decimal("0.00"),
        total_sales=total_sales,
        orders_count=orders_count,
        average_order_value=average_order_value,
        currency_code=currency_code,
        currency_count=currency_count,
        refunded_orders=refunded_orders,
        cancelled_orders=cancelled_orders,
    )


class SalesServiceTests(unittest.TestCase):
    def test_sales_summary_allows_negative_net_sales_after_filtering(self):
        metrics = build_metrics(
            gross_sales=Decimal("0.00"),
            discounts=Decimal("56.84"),
            net_sales=Decimal("-56.84"),
            total_sales=Decimal("0.00"),
            orders_count=1,
            average_order_value=Decimal("0.00"),
        )

        result = SalesService(
            StubSalesRepository(metrics=metrics)
        ).get_sales_summary(SalesFilters())

        self.assertEqual(result.net_sales, -56.84)

    def test_builds_chronological_chart_response_and_highlights(self):
        repository = StubSalesRepository(
            [
                (date(2026, 1, 1), Decimal("100.50"), "USD"),
                (date(2026, 1, 2), Decimal("250.25"), "USD"),
            ]
        )

        result = SalesService(repository).get_revenue_trend(SalesFilters(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        ))

        self.assertEqual(
            repository.received_dates, (date(2026, 1, 1), date(2026, 1, 31))
        )
        self.assertEqual(result.currency, "USD")
        self.assertEqual(result.interval, "daily")
        self.assertEqual(
            [point.date for point in result.data],
            [date(2026, 1, 1), date(2026, 1, 2)],
        )
        self.assertAlmostEqual(result.highlights.total_revenue, 350.75)
        self.assertEqual(result.highlights.highest_revenue_date, date(2026, 1, 2))
        self.assertAlmostEqual(result.highlights.highest_daily_revenue, 250.25)

    def test_returns_clean_empty_response(self):
        result = SalesService(StubSalesRepository([])).get_revenue_trend(SalesFilters())

        self.assertIsNone(result.currency)
        self.assertEqual(result.data, [])
        self.assertIsNone(result.highlights)

    def test_rejects_reversed_date_range(self):
        with self.assertRaisesRegex(
            ValueError, "start_date must be on or before end_date"
        ):
            build_sales_filters(date(2026, 2, 1), date(2026, 1, 1))

    def test_sales_summary_preserves_sal_001_response_defaults(self):
        metrics = build_metrics(
            gross_sales=None,
            discounts=None,
            total_sales=None,
            orders_count=0,
            average_order_value=None,
        )

        result = SalesService(StubSalesRepository(metrics=metrics)).get_sales_summary()

        self.assertEqual(
            result.model_dump(),
            {
                "gross_sales": 0.0,
                "discounts": 0.0,
                "returns_refunds": 0.0,
                "net_sales": 0.0,
                "shipping": 0.0,
                "taxes": 0.0,
                "total_sales": 0.0,
                "orders_count": 0,
                "average_order_value": 0.0,
                "currency": "USD",
                "last_updated_at": None,
            },
        )

    def test_filter_options_are_clean_grouped_and_postgresql_backed(self):
        response = SalesService(StubSalesRepository()).get_filter_options()

        self.assertEqual(
            [(option.name, option.values) for option in response.sales_channels],
            [
                ("Online Store", ["web"]),
                ("Point of Sale", ["pos"]),
                ("Other/app-specific channels", ["mobile_app"]),
            ],
        )
        self.assertEqual(response.order_statuses, ["PAID", "REFUNDED"])
        self.assertEqual(response.currencies, ["CAD", "USD"])

    def test_no_orders_rule_uses_reliable_zero_only(self):
        service = SalesService(
            StubSalesRepository(metrics=build_metrics(
                gross_sales=None,
                discounts=None,
                total_sales=None,
                orders_count=0,
                average_order_value=None,
                currency_code=None,
                currency_count=0,
            ))
        )

        response = service.get_action_needed(SalesFilters())

        self.assertTrue(response.has_sufficient_data)
        self.assertEqual([action.id for action in response.actions], ["sales_no_orders"])
        self.assertEqual(response.actions[0].action_label, "Go to Orders")
        self.assertEqual(response.actions[0].action_url, "shopify://admin/orders")

        missing_response = SalesService(
            StubSalesRepository(metrics=build_metrics(
                gross_sales=None,
                discounts=None,
                total_sales=None,
                orders_count=None,
                average_order_value=None,
                currency_code=None,
                currency_count=0,
            ))
        ).get_action_needed(SalesFilters())
        self.assertFalse(missing_response.has_sufficient_data)
        self.assertEqual(missing_response.actions, [])

    def test_low_aov_rule_respects_threshold_and_missing_values(self):
        cases = (
            (Decimal("49.99"), True),
            (Decimal("50.00"), False),
            (Decimal("50.01"), False),
            (None, False),
        )
        for average_order_value, expected in cases:
            with self.subTest(average_order_value=average_order_value):
                response = SalesService(
                    StubSalesRepository(metrics=build_metrics(
                        average_order_value=average_order_value
                    )),
                    low_aov_threshold=Decimal("50.00"),
                ).get_action_needed(SalesFilters())
                action_ids = {action.id for action in response.actions}
                self.assertEqual("sales_low_average_order_value" in action_ids, expected)

    def test_high_discount_rule_handles_boundaries_and_invalid_denominators(self):
        cases = (
            (Decimal("100.00"), Decimal("19.99"), False),
            (Decimal("100.00"), Decimal("20.00"), False),
            (Decimal("100.00"), Decimal("20.01"), True),
            (Decimal("0.00"), Decimal("10.00"), False),
            (None, Decimal("10.00"), False),
            (Decimal("100.00"), None, False),
        )
        for gross_sales, discounts, expected in cases:
            with self.subTest(gross_sales=gross_sales, discounts=discounts):
                response = SalesService(
                    StubSalesRepository(metrics=build_metrics(
                        gross_sales=gross_sales,
                        discounts=discounts,
                    )),
                    high_discount_rate_threshold=Decimal("0.20"),
                ).get_action_needed(SalesFilters())
                action_ids = {action.id for action in response.actions}
                self.assertEqual("sales_high_discount_usage" in action_ids, expected)

    def test_refund_and_cancellation_rule_respects_independent_thresholds(self):
        cases = (
            (1, 0, False),
            (2, 0, True),
            (0, 1, False),
            (0, 2, True),
            (2, 2, True),
            (None, None, False),
        )
        for refunded_orders, cancelled_orders, expected in cases:
            with self.subTest(
                refunded_orders=refunded_orders,
                cancelled_orders=cancelled_orders,
            ):
                response = SalesService(
                    StubSalesRepository(metrics=build_metrics(
                        orders_count=10,
                        refunded_orders=refunded_orders,
                        cancelled_orders=cancelled_orders,
                    )),
                    refund_rate_threshold=Decimal("0.10"),
                    cancellation_rate_threshold=Decimal("0.10"),
                ).get_action_needed(SalesFilters())
                matching = [
                    action for action in response.actions
                    if action.id == "sales_refund_cancellation_spike"
                ]
                self.assertEqual(bool(matching), expected)
                if refunded_orders == 2 and cancelled_orders == 2:
                    self.assertEqual(
                        matching[0].message,
                        "Refunded orders represent 20% of orders and cancelled "
                        "orders represent 20% of orders.",
                    )
                    self.assertTrue(matching[0].download_available)

    def test_refund_cancellation_export_groups_products_and_escapes_csv(self):
        refunded_at = datetime(2026, 8, 9, 10, 30, tzinfo=timezone.utc)
        cancelled_at = datetime(2026, 8, 10, 8, 15, tzinfo=timezone.utc)
        repository = StubSalesRepository(rows=[
            SalesActionExportRow(
                "gid://shopify/Order/1",
                "=Formula product",
                "REFUNDED",
                Decimal("25.50"),
                "+Customer request",
                cancelled_at,
                refunded_at,
            ),
            SalesActionExportRow(
                "gid://shopify/Order/1",
                "Second product",
                "REFUNDED",
                Decimal("25.50"),
                "+Customer request",
                cancelled_at,
                refunded_at,
            ),
        ])

        export = SalesService(repository).get_action_export(
            "sales_refund_cancellation_spike",
            SalesFilters(
                start_date=date(2026, 8, 1), end_date=date(2026, 8, 10)
            ),
        )
        records = list(csv.DictReader(io.StringIO(export.content)))

        self.assertEqual(export.filename, "sales-refund-cancellation-records.csv")
        self.assertEqual(repository.received_dates, (date(2026, 8, 1), date(2026, 8, 10)))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["product_name"], "'=Formula product | Second product")
        self.assertEqual(records[0]["amount_refunded"], "25.50")
        self.assertEqual(records[0]["refund_reason"], "'+Customer request")
        self.assertEqual(records[0]["cancelled_at"], cancelled_at.isoformat())
        self.assertEqual(records[0]["refunded_date"], refunded_at.isoformat())

    def test_action_export_rejects_unsupported_actions(self):
        with self.assertRaises(LookupError):
            SalesService(StubSalesRepository()).get_action_export(
                "sales_low_average_order_value", SalesFilters()
            )

    def test_actions_are_stable_unique_limited_and_date_filtered(self):
        repository = StubSalesRepository(metrics=build_metrics(
            gross_sales=Decimal("100.00"),
            discounts=Decimal("25.00"),
            average_order_value=Decimal("25.00"),
            refunded_orders=2,
            orders_count=10,
        ))

        response = SalesService(repository).get_action_needed(SalesFilters(
            start_date=date(2026, 8, 1), end_date=date(2026, 8, 10)
        ))

        self.assertEqual(repository.received_dates, (date(2026, 8, 1), date(2026, 8, 10)))
        self.assertEqual(
            [action.id for action in response.actions],
            [
                "sales_refund_cancellation_spike",
                "sales_low_average_order_value",
                "sales_high_discount_usage",
            ],
        )
        self.assertEqual(len(response.actions), len({action.id for action in response.actions}))
        self.assertLessEqual(len(response.actions), 5)
        self.assertEqual(
            response.actions[0].message,
            "Refunded orders represent 20% of orders.",
        )
        self.assertEqual(response.actions[1].message, "Average order value is USD 25.00.")
        self.assertEqual(response.actions[2].message, "Discounts represent 25% of gross sales.")
        self.assertEqual(
            [(action.action_label, action.action_url) for action in response.actions],
            [
                ("Go to Orders", "shopify://admin/orders"),
                ("Go to Products", "shopify://admin/products"),
                ("Go to Discount", "shopify://admin/discounts"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
