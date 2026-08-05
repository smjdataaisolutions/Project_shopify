from datetime import date
from decimal import Decimal

from app.repositories.sales_repository import SalesRepository
from app.schemas.sales import (
    RevenueTrendHighlights,
    RevenueTrendPoint,
    RevenueTrendResponse,
)


class SalesService:
    """Business logic for sales analytics."""

    def __init__(self, repository: SalesRepository) -> None:
        self.repository = repository

    def get_revenue_trend(
        self,
        start_date: date | None,
        end_date: date | None,
    ) -> RevenueTrendResponse:
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")

        rows = self.repository.get_revenue_trend(start_date, end_date)
        points = [
            RevenueTrendPoint(date=period, revenue=float(revenue))
            for period, revenue, _currency in rows
        ]
        currency = next(
            (currency for _period, _revenue, currency in rows if currency), None
        )

        highlights = None
        if points:
            highest_period, highest_revenue, _currency = max(
                rows, key=lambda row: row[1]
            )
            highlights = RevenueTrendHighlights(
                total_revenue=float(
                    sum((revenue for _period, revenue, _currency in rows), Decimal(0))
                ),
                highest_revenue_date=highest_period,
                highest_daily_revenue=float(highest_revenue),
            )

        return RevenueTrendResponse(
            currency=currency,
            interval="daily",
            data=points,
            highlights=highlights,
        )
