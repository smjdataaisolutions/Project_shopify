from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.inventory_repository import InventoryKpiInputs
from app.routers.inventory import get_inventory_kpis, router
from app.schemas.inventory import InventoryKpiResponse


class InventoryApiTests(unittest.TestCase):
    @patch("app.routers.inventory.InventoryRepository.get_kpi_inputs")
    def test_endpoint_returns_clean_response(self, get_inputs):
        get_inputs.return_value = InventoryKpiInputs(320, 12, 3, 2, 680)

        response = get_inventory_kpis(
            db=object(),
            settings=SimpleNamespace(low_stock_threshold=10),
        )

        self.assertEqual(
            response.model_dump(),
            {
                "total_inventory_units": 320,
                "in_stock_products": 12,
                "low_stock_products": 3,
                "out_of_stock_products": 2,
                "sell_through_rate": 68.0,
                "days_of_inventory_remaining": 14.1,
            },
        )

    def test_route_uses_documented_path_and_schema(self):
        route = next(
            route for route in router.routes
            if route.path == "/api/analytics/inventory/kpis"
        )

        self.assertEqual(route.response_model, InventoryKpiResponse)
        self.assertIn("GET", route.methods)

    @patch("app.routers.inventory.InventoryRepository.get_kpi_inputs")
    def test_endpoint_sanitizes_database_errors(self, get_inputs):
        get_inputs.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_inventory_kpis(
                db=object(),
                settings=SimpleNamespace(low_stock_threshold=10),
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve inventory KPI data.",
        )
        self.assertNotIn("credentials", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
