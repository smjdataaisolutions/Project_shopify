import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from app.repositories.dashboard_repository import (
    InventoryExposureResult,
    OverviewFilters,
    OverviewSalesMetrics,
    ProductSalesConcentrationResult,
    ProductSalesMetric,
)
from app.schemas.dashboard import BusinessHighlightsResponse
from app.routers.dashboard import router
from app.services.dashboard_service import DashboardService


def sales(total, orders):
    return OverviewSalesMetrics(Decimal(total), orders, "USD")


def product(product_id, amount, units=1):
    return ProductSalesMetric(
        product_id=product_id,
        product_title=f"Product {product_id}",
        units_sold=units,
        net_product_sales=Decimal(amount),
        currency_code="USD",
    )


class HighlightRepositoryStub:
    def __init__(self, current, previous, products=None, exposure=None):
        self.sales_results = [current, previous]
        self.sales_filters = []
        product_rows = products or []
        self.concentration = ProductSalesConcentrationResult(
            top_products=product_rows[:3],
            product_count=len(product_rows),
            total_net_product_sales=sum(
                (row.net_product_sales for row in product_rows), Decimal("0")
            ),
            currency_code="USD",
        )
        self.exposure = exposure or InventoryExposureResult(
            inventory_available=True,
            affected_product_count=0,
            low_stock_product_count=0,
            out_of_stock_product_count=0,
            affected_net_product_sales=Decimal("0"),
            affected_units_sold=0,
            highest_impact_product=None,
            highest_impact_inventory_status=None,
            inventory_as_of=datetime(2026, 8, 13, tzinfo=timezone.utc),
            currency_code="USD",
        )

    def get_sales_metrics(self, filters):
        self.sales_filters.append(filters)
        return self.sales_results.pop(0)

    def get_product_sales_concentration(self, filters):
        return self.concentration

    def get_inventory_exposure(self, threshold, filters):
        return self.exposure


class BusinessHighlightTests(unittest.TestCase):
    def build(self, current, previous, products=None, exposure=None, **dates):
        repository = HighlightRepositoryStub(
            current, previous, products, exposure
        )
        response = DashboardService(repository, 10).get_business_highlights(
            OverviewFilters(
                start_date=dates.get("start", date(2026, 8, 1)),
                end_date=dates.get("end", date(2026, 8, 10)),
                financial_statuses=("PAID",),
            )
        )
        return repository, response

    def test_builds_equal_length_previous_period_and_preserves_filters(self):
        repository, response = self.build(sales("105", 2), sales("100", 2))

        momentum = response.highlights[0]
        self.assertEqual(momentum.status, "positive")
        self.assertEqual(momentum.total_sales_change_percentage, 5.0)
        self.assertEqual(momentum.previous_period.start_date, date(2026, 7, 22))
        self.assertEqual(momentum.previous_period.end_date, date(2026, 7, 31))
        self.assertEqual(
            repository.sales_filters[1].financial_statuses, ("PAID",)
        )

    def test_exact_negative_boundary_is_attention(self):
        _, response = self.build(sales("95", 1), sales("100", 1))
        self.assertEqual(response.highlights[0].status, "attention")

    def test_change_inside_boundary_is_stable(self):
        _, response = self.build(sales("104.99", 1), sales("100", 1))
        self.assertEqual(response.highlights[0].status, "stable")

    def test_single_day_crosses_year_boundary(self):
        _, response = self.build(
            sales("10", 1), sales("5", 1),
            start=date(2026, 1, 1), end=date(2026, 1, 1),
        )
        period = response.highlights[0].previous_period
        self.assertEqual((period.start_date, period.end_date), (
            date(2025, 12, 31), date(2025, 12, 31)
        ))

    def test_previous_zero_current_positive_is_new_activity(self):
        _, response = self.build(sales("20", 2), sales("0", 0))
        momentum = response.highlights[0]
        self.assertEqual(momentum.status, "new_activity")
        self.assertIsNone(momentum.total_sales_change_percentage)

    def test_both_periods_zero_are_no_activity(self):
        _, response = self.build(sales("0", 0), sales("0", 0))
        momentum = response.highlights[0]
        self.assertEqual(momentum.status, "no_activity")
        self.assertEqual(momentum.total_sales_change_percentage, 0.0)

    def test_current_zero_after_previous_sales_is_attention(self):
        _, response = self.build(sales("0", 0), sales("100", 2))
        self.assertEqual(response.highlights[0].status, "attention")
        self.assertEqual(response.highlights[0].total_sales_change_percentage, -100.0)

    def test_leap_day_period_is_shifted_by_inclusive_days(self):
        _, response = self.build(
            sales("20", 2), sales("10", 1),
            start=date(2024, 2, 28), end=date(2024, 2, 29),
        )
        period = response.highlights[0].previous_period
        self.assertEqual((period.start_date, period.end_date), (
            date(2024, 2, 26), date(2024, 2, 27)
        ))

    def test_product_concentration_groups_and_uses_deterministic_result(self):
        products = [product("1", "50", 5), product("2", "30"), product("3", "20")]
        _, response = self.build(sales("100", 2), sales("100", 2), products)

        concentration = response.highlights[1]
        self.assertEqual(concentration.status, "high")
        self.assertEqual(concentration.top_product.product_id, "1")
        self.assertEqual(concentration.top_product.contribution_percentage, 50.0)
        self.assertEqual(concentration.top_group_contribution_percentage, 100.0)

    def test_non_positive_product_sales_are_unavailable(self):
        _, response = self.build(
            sales("0", 0), sales("0", 0), [product("1", "-1")]
        )
        self.assertEqual(response.highlights[1].status, "unavailable")

    def test_two_products_are_described_without_claiming_top_three(self):
        _, response = self.build(
            sales("30", 2), sales("20", 1),
            [product("1", "20"), product("2", "10")],
        )
        concentration = response.highlights[1]
        self.assertEqual(concentration.products_in_top_group, 2)
        self.assertIn("2 products sold", concentration.supporting_text)

    def test_inventory_exposure_uses_current_status_and_sales_exposure(self):
        top = product("1", "42", 3)
        exposure = InventoryExposureResult(
            inventory_available=True,
            affected_product_count=2,
            low_stock_product_count=1,
            out_of_stock_product_count=1,
            affected_net_product_sales=Decimal("60"),
            affected_units_sold=5,
            highest_impact_product=top,
            highest_impact_inventory_status="out_of_stock",
            inventory_as_of=datetime(2026, 8, 13, tzinfo=timezone.utc),
            currency_code="USD",
        )
        _, response = self.build(sales("100", 2), sales("90", 2), exposure=exposure)
        highlight = response.highlights[2]
        self.assertEqual(highlight.status, "critical")
        self.assertEqual(highlight.highest_impact_product.product_id, "1")
        self.assertIn("current inventory levels", highlight.helper_text)

    def test_missing_inventory_is_unavailable_not_zero(self):
        exposure = InventoryExposureResult(
            inventory_available=False,
            affected_product_count=0,
            low_stock_product_count=0,
            out_of_stock_product_count=0,
            affected_net_product_sales=Decimal("0"),
            affected_units_sold=0,
            highest_impact_product=None,
            highest_impact_inventory_status=None,
            inventory_as_of=None,
            currency_code=None,
        )
        _, response = self.build(sales("10", 1), sales("10", 1), exposure=exposure)
        highlight = response.highlights[2]
        self.assertEqual(highlight.status, "unavailable")
        self.assertIsNone(highlight.affected_net_product_sales)

    def test_route_retains_existing_contract_path(self):
        route = next(
            route for route in router.routes
            if route.path == "/api/analytics/overview/business-highlights"
        )
        self.assertEqual(route.response_model, BusinessHighlightsResponse)


if __name__ == "__main__":
    unittest.main()
