from decimal import Decimal
from types import SimpleNamespace
import unittest

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.routers.dashboard import get_business_highlights, router
from app.schemas.dashboard import BusinessHighlightsResponse


class StubResult:
    def __init__(self, row):
        self.row = row

    def one(self):
        return self.row

    def first(self):
        return self.row


class StubSession:
    def __init__(self):
        self.rows = iter(
            [
                SimpleNamespace(
                    total_revenue=Decimal("50"),
                    total_orders=2,
                    currency_code="USD",
                ),
                SimpleNamespace(
                    products_with_inventory=2,
                    low_stock_count=1,
                    out_of_stock_count=0,
                ),
                SimpleNamespace(
                    product_id="product-1",
                    product_title="Product One",
                    units_sold=2,
                    product_revenue=Decimal("50"),
                    currency_code="USD",
                ),
            ]
        )

    def execute(self, _statement):
        return StubResult(next(self.rows))


class FailingSession:
    def execute(self, _statement):
        raise SQLAlchemyError("database unavailable")


class DashboardHighlightsApiTests(unittest.TestCase):
    def test_endpoint_returns_schema_compliant_highlights(self):
        response = get_business_highlights(db=StubSession())

        self.assertIsInstance(response, BusinessHighlightsResponse)
        self.assertEqual(response.currency_code, "USD")
        self.assertEqual(len(response.highlights), 3)

    def test_route_uses_documented_path_and_response_model(self):
        route = next(
            route
            for route in router.routes
            if route.path == "/api/analytics/overview/business-highlights"
        )

        self.assertEqual(route.response_model, BusinessHighlightsResponse)
        self.assertIn("GET", route.methods)

    def test_database_failure_returns_sanitized_500(self):
        with self.assertLogs("app.routers.dashboard", level="ERROR"):
            with self.assertRaises(HTTPException) as context:
                get_business_highlights(db=FailingSession())

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(
            context.exception.detail,
            "Unable to retrieve business highlights.",
        )


if __name__ == "__main__":
    unittest.main()
