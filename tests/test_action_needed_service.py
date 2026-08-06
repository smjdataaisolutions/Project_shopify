from decimal import Decimal
import unittest

from app.repositories.dashboard_repository import (
    InventoryHealthMetrics,
    OverviewSalesMetrics,
)
from app.services.dashboard_service import ActionNeededService


class StubDashboardRepository:
    def __init__(self, sales, inventory):
        self.sales = sales
        self.inventory = inventory
        self.inventory_threshold = None

    def get_sales_metrics(self):
        return self.sales

    def get_inventory_health(self, low_stock_threshold):
        self.inventory_threshold = low_stock_threshold
        return self.inventory


def build_service(
    *,
    total_revenue=Decimal("500.00"),
    total_orders=5,
    low_stock_count=0,
    out_of_stock_count=0,
    products_with_inventory=1,
):
    repository = StubDashboardRepository(
        OverviewSalesMetrics(total_revenue, total_orders, "USD"),
        InventoryHealthMetrics(
            products_with_inventory,
            low_stock_count,
            out_of_stock_count,
        ),
    )
    return ActionNeededService(repository, Decimal("50.00")), repository


class ActionNeededServiceTests(unittest.TestCase):
    def test_returns_all_applicable_actions_in_priority_order(self):
        service, repository = build_service(
            total_revenue=Decimal("40.00"),
            total_orders=2,
            low_stock_count=5,
            out_of_stock_count=2,
        )

        response = service.get_actions()

        self.assertEqual(repository.inventory_threshold, 10)
        self.assertEqual(
            [action.id for action in response.actions],
            [
                "inventory_out_of_stock",
                "inventory_low_stock",
                "sales_low_average_order_value",
            ],
        )
        self.assertEqual(
            [action.priority for action in response.actions],
            ["critical", "warning", "recommendation"],
        )

    def test_no_orders_is_a_warning_and_does_not_emit_low_aov(self):
        service, _repository = build_service(
            total_revenue=None,
            total_orders=0,
            products_with_inventory=0,
        )

        response = service.get_actions()

        self.assertEqual(len(response.actions), 1)
        self.assertEqual(response.actions[0].id, "sales_no_orders")
        self.assertEqual(response.actions[0].priority, "warning")

    def test_ignores_missing_revenue_for_existing_orders(self):
        service, _repository = build_service(
            total_revenue=None,
            total_orders=3,
            products_with_inventory=0,
        )

        self.assertEqual(service.get_actions().actions, [])

    def test_returns_empty_response_when_no_rules_apply(self):
        service, _repository = build_service()

        self.assertEqual(
            service.get_actions().model_dump(mode="json"),
            {"actions": []},
        )

    def test_uses_distinct_action_ids(self):
        service, _repository = build_service(
            total_revenue=Decimal("10.00"),
            total_orders=1,
            low_stock_count=3,
            out_of_stock_count=3,
        )

        action_ids = [action.id for action in service.get_actions().actions]

        self.assertEqual(len(action_ids), len(set(action_ids)))


if __name__ == "__main__":
    unittest.main()
