import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.routers.dashboard import (
    download_action_needed_records,
    get_action_needed,
    router,
)
from app.repositories.dashboard_repository import OverviewFilters
from app.schemas.dashboard import ActionNeededResponse


class ActionNeededApiTests(unittest.TestCase):
    @patch("app.routers.dashboard.ActionNeededService.get_actions")
    def test_returns_clean_response(self, get_actions):
        get_actions.return_value = ActionNeededResponse(
            actions=[
                {
                    "id": "inventory_out_of_stock",
                    "priority": "critical",
                    "category": "inventory",
                    "title": "Products are out of stock",
                    "message": "2 products are currently unavailable.",
                    "affected_products": [
                        {
                            "product_id": "product-1",
                            "product_title": "Example product",
                            "inventory_quantity": 0,
                        }
                    ],
                    "recommended_action": "Restock inventory immediately.",
                    "action_label": "Go to Inventory",
                    "action_url": "/app/inventory",
                    "download_available": True,
                }
            ]
        )

        response = get_action_needed(filters=OverviewFilters(), db=object())

        self.assertEqual(
            response.model_dump(mode="json"),
            {
                "actions": [
                    {
                        "id": "inventory_out_of_stock",
                        "priority": "critical",
                        "category": "inventory",
                        "title": "Products are out of stock",
                        "message": "2 products are currently unavailable.",
                        "affected_products": [
                            {
                                "product_id": "product-1",
                                "product_title": "Example product",
                                "inventory_quantity": 0,
                            }
                        ],
                        "recommended_action": "Restock inventory immediately.",
                        "action_label": "Go to Inventory",
                        "action_url": "/app/inventory",
                        "download_available": True,
                    }
                ]
            },
        )

    def test_route_uses_documented_path_and_response_model(self):
        route = next(
            route
            for route in router.routes
            if route.path == "/api/analytics/overview/action-needed"
        )

        self.assertEqual(route.response_model, ActionNeededResponse)
        self.assertIn("GET", route.methods)

    @patch("app.routers.dashboard.ActionNeededService.get_action_export")
    def test_download_route_returns_csv_attachment(self, get_action_export):
        from app.services.dashboard_service import OverviewActionCsvExport

        get_action_export.return_value = OverviewActionCsvExport(
            filename="low_stock_products.csv",
            content="product_id,affected_product_name\r\np-1,Example\r\n",
        )

        response = download_action_needed_records(
            "inventory_low_stock", filters=OverviewFilters(), db=object()
        )

        self.assertEqual(response.media_type, "text/csv")
        self.assertEqual(
            response.headers["content-disposition"],
            'attachment; filename="low_stock_products.csv"',
        )

    def test_download_route_uses_documented_path(self):
        route = next(
            route
            for route in router.routes
            if route.path
            == "/api/analytics/overview/action-needed/{action_id}/download"
        )
        self.assertIn("GET", route.methods)

    @patch("app.routers.dashboard.DashboardRepository.get_sales_metrics")
    def test_sanitizes_database_errors(self, get_sales_metrics):
        get_sales_metrics.side_effect = SQLAlchemyError("database credentials")

        with self.assertRaises(HTTPException) as context:
            get_action_needed(filters=OverviewFilters(), db=object())

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve action needed recommendations.",
        )
        self.assertNotIn("credentials", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
