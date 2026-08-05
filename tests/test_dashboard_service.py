from decimal import Decimal
import unittest

from app.repositories.dashboard_repository import (
    InventoryHealthMetrics,
    OverviewSalesMetrics,
    TopProductMetrics,
)
from app.services.dashboard_service import DashboardService


class StubDashboardRepository:
    def __init__(self, sales, inventory, top_product):
        self.sales = sales
        self.inventory = inventory
        self.top_product = top_product
        self.inventory_threshold = None

    def get_sales_metrics(self):
        return self.sales

    def get_inventory_health(self, threshold):
        self.inventory_threshold = threshold
        return self.inventory

    def get_top_selling_product(self):
        return self.top_product


def make_repository(
    sales=None,
    inventory=None,
    top_product=None,
):
    return StubDashboardRepository(
        sales
        or OverviewSalesMetrics(
            total_revenue=None,
            total_orders=0,
            currency_code=None,
        ),
        inventory
        or InventoryHealthMetrics(
            products_with_inventory=0,
            low_stock_count=0,
            out_of_stock_count=0,
        ),
        top_product,
    )


class DashboardServiceTests(unittest.TestCase):
    def test_builds_three_ordered_deterministic_highlights(self):
        repository = make_repository(
            sales=OverviewSalesMetrics(Decimal("110.00"), 3, "USD"),
            inventory=InventoryHealthMetrics(5, 2, 1),
            top_product=TopProductMetrics(
                product_id="gid://shopify/Product/1",
                product_title="Classic T-Shirt",
                units_sold=4,
                product_revenue=Decimal("80.00"),
                currency_code="USD",
            ),
        )

        response = DashboardService(repository).get_business_highlights()

        self.assertEqual(repository.inventory_threshold, 10)
        self.assertEqual(
            [highlight.id for highlight in response.highlights],
            ["sales_performance", "inventory_health", "top_selling_product"],
        )
        self.assertEqual(response.currency_code, "USD")

        sales = response.highlights[0]
        self.assertEqual(sales.severity, "info")
        self.assertEqual(
            sales.message,
            "USD 110.00 in revenue was generated from 3 orders.",
        )
        self.assertEqual(sales.supporting_text, "Average order value was USD 36.67.")
        self.assertEqual(sales.metrics.average_order_value, 36.67)

        inventory = response.highlights[1]
        self.assertEqual(inventory.severity, "critical")
        self.assertEqual(
            inventory.message,
            "2 products are running low in stock and 1 product is out of stock.",
        )

        top_product = response.highlights[2]
        self.assertEqual(top_product.severity, "info")
        self.assertIn("4 units sold", top_product.message)
        self.assertEqual(top_product.metrics.product_id, "gid://shopify/Product/1")

    def test_omits_highlights_when_source_data_is_unavailable(self):
        response = DashboardService(make_repository()).get_business_highlights()

        self.assertIsNone(response.currency_code)
        self.assertEqual(response.highlights, [])

    def test_inventory_severity_rules_and_boundary_message(self):
        cases = [
            (InventoryHealthMetrics(2, 0, 0), "positive"),
            (InventoryHealthMetrics(2, 1, 0), "warning"),
            (InventoryHealthMetrics(2, 0, 1), "critical"),
        ]
        for inventory_metrics, expected_severity in cases:
            with self.subTest(expected_severity=expected_severity):
                response = DashboardService(
                    make_repository(inventory=inventory_metrics)
                ).get_business_highlights()

                self.assertEqual(len(response.highlights), 1)
                self.assertEqual(response.highlights[0].severity, expected_severity)

    def test_handles_missing_currency_and_product_title(self):
        response = DashboardService(
            make_repository(
                sales=OverviewSalesMetrics(Decimal("10"), 1, None),
                top_product=TopProductMetrics(
                    product_id="product-1",
                    product_title=None,
                    units_sold=1,
                    product_revenue=Decimal("10"),
                    currency_code=None,
                ),
            )
        ).get_business_highlights()

        self.assertEqual(
            response.highlights[0].message,
            "10.00 in revenue was generated from 1 order.",
        )
        self.assertEqual(
            response.highlights[1].message,
            "Untitled product is the top-selling product with 1 unit sold.",
        )


if __name__ == "__main__":
    unittest.main()
