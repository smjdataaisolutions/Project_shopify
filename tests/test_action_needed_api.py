import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.routers.dashboard import get_action_needed, router
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
