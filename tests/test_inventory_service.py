from datetime import date
import unittest

from app.repositories.inventory_repository import InventoryFilters, InventoryKpiInputs
from app.services.inventory_service import InventoryService


class StubInventoryRepository:
    def __init__(self, inputs: InventoryKpiInputs) -> None:
        self.inputs = inputs
        self.call = None

    def get_kpi_inputs(
        self, start_date, end_date, low_stock_threshold, filters, level
    ):
        self.call = (start_date, end_date, low_stock_threshold, filters, level)
        return self.inputs


class InventoryServiceTests(unittest.TestCase):
    def test_calculates_inventory_velocity_kpis(self):
        repository = StubInventoryRepository(
            InventoryKpiInputs(
                total_inventory_units=320,
                in_stock_products=12,
                low_stock_products=3,
                out_of_stock_products=2,
                units_sold=680,
            )
        )
        service = InventoryService(
            repository,
            low_stock_threshold=10,
            today=lambda: date(2026, 8, 11),
        )

        response = service.get_kpis()

        self.assertEqual(response.sell_through_rate, 68.0)
        self.assertEqual(response.days_of_inventory_remaining, 14.1)
        self.assertEqual(
            repository.call,
            (
                date(2026, 7, 13),
                date(2026, 8, 11),
                10,
                InventoryFilters(),
                "variant",
            ),
        )

    def test_no_sales_returns_zero_sell_through_and_unknown_days(self):
        service = InventoryService(
            StubInventoryRepository(InventoryKpiInputs(25, 1, 0, 0, 0)),
            low_stock_threshold=10,
        )

        response = service.get_kpis()

        self.assertEqual(response.sell_through_rate, 0.0)
        self.assertIsNone(response.days_of_inventory_remaining)

    def test_empty_data_returns_safe_counts_and_null_derived_metrics(self):
        service = InventoryService(
            StubInventoryRepository(InventoryKpiInputs(0, 0, 0, 0, 0)),
            low_stock_threshold=10,
        )

        self.assertEqual(
            service.get_kpis().model_dump(),
            {
                "total_inventory_units": 0,
                "in_stock_products": 0,
                "low_stock_products": 0,
                "out_of_stock_products": 0,
                "sell_through_rate": None,
                "days_of_inventory_remaining": None,
            },
        )

    def test_zero_inventory_with_sales_returns_zero_days(self):
        service = InventoryService(
            StubInventoryRepository(InventoryKpiInputs(0, 0, 0, 2, 15)),
            low_stock_threshold=10,
        )

        response = service.get_kpis()

        self.assertEqual(response.sell_through_rate, 100.0)
        self.assertEqual(response.days_of_inventory_remaining, 0.0)


if __name__ == "__main__":
    unittest.main()
