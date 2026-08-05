from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Date, func, select
from sqlalchemy.orm import Session

from app.db.models import Order


class SalesRepository:
    """Database queries for sales analytics."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_revenue_trend(
        self,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple[date, Decimal, str | None]]:
        """Return daily revenue aggregates ordered by the Shopify processed date."""
        period = func.date_trunc("day", Order.processed_at).cast(Date).label("period")
        statement = (
            select(
                period,
                func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
                func.max(Order.currency_code).label("currency"),
            )
            .where(Order.processed_at.is_not(None))
            .group_by(period)
            .order_by(period)
        )

        if start_date:
            statement = statement.where(Order.processed_at >= start_date)
        if end_date:
            statement = statement.where(Order.processed_at < end_date + timedelta(days=1))

        return list(self.db.execute(statement).all())
