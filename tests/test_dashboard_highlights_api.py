import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.dashboard_repository import OverviewFilters
from app.routers.dashboard import get_business_highlights, router
from app.schemas.dashboard import BusinessHighlightsResponse


class DashboardHighlightsApiTests(unittest.TestCase):
    @patch("app.routers.dashboard.DashboardService.get_business_highlights")
    def test_endpoint_returns_schema_compliant_highlights(self, get_highlights):
        get_highlights.return_value = BusinessHighlightsResponse(
            currency_code="USD",
            highlights=[],
        )

        response = get_business_highlights(
            filters=OverviewFilters(), db=object()
        )

        self.assertIsInstance(response, BusinessHighlightsResponse)
        self.assertEqual(response.currency_code, "USD")
        self.assertEqual(response.highlights, [])

    def test_route_uses_documented_path_and_response_model(self):
        route = next(
            route
            for route in router.routes
            if route.path == "/api/analytics/overview/business-highlights"
        )

        self.assertEqual(route.response_model, BusinessHighlightsResponse)
        self.assertIn("GET", route.methods)

    @patch("app.routers.dashboard.DashboardRepository.get_sales_metrics")
    def test_database_failure_returns_sanitized_500(self, get_sales_metrics):
        get_sales_metrics.side_effect = SQLAlchemyError("database unavailable")
        with self.assertLogs("app.routers.dashboard", level="ERROR"):
            with self.assertRaises(HTTPException) as context:
                get_business_highlights(
                    filters=OverviewFilters(), db=object()
                )

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve business highlights.",
        )


if __name__ == "__main__":
    unittest.main()
