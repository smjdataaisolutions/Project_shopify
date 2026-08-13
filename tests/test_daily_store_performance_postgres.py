import os
import unittest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.dashboard_repository import DashboardRepository, OverviewFilters
from app.services.dashboard_service import DashboardService


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class DailyStorePerformancePostgresTests(unittest.TestCase):
    def test_complete_totals_reconcile_with_overview_kpis(self):
        with SessionLocal() as db:
            service = DashboardService(
                DashboardRepository(db),
                get_settings().low_stock_threshold,
            )
            filters = OverviewFilters()
            daily = service.get_daily_store_performance(
                1, 100, "date", "desc", filters
            )
            overview = service.get_summary(filters)

        dates = [item.date for item in daily.items]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(daily.summary.total_sales, overview.total_revenue)
        self.assertEqual(daily.summary.orders, overview.total_orders)
        self.assertEqual(daily.summary.units_sold, overview.units_sold)
        self.assertEqual(
            daily.summary.average_order_value,
            round(
                daily.summary.total_sales / daily.summary.orders
                if daily.summary.orders
                else 0,
                2,
            ),
        )

    def test_filters_sorting_and_pagination_use_real_daily_rows(self):
        with SessionLocal() as db:
            repository = DashboardRepository(db)
            service = DashboardService(
                repository,
                get_settings().low_stock_threshold,
            )
            options = repository.get_filter_options()
            filters = OverviewFilters(
                financial_statuses=options.financial_statuses[:1]
            )
            filtered = service.get_daily_store_performance(
                1, 1, "total_sales", "desc", filters
            )
            overview = service.get_summary(filters)
            all_rows = service.get_daily_store_performance(
                1, 100, "average_order_value", "asc", filters
            )

        self.assertEqual(filtered.pagination.page_size, 1)
        self.assertLessEqual(len(filtered.items), 1)
        self.assertEqual(filtered.summary.total_sales, overview.total_revenue)
        self.assertEqual(filtered.summary.orders, overview.total_orders)
        self.assertEqual(filtered.summary.units_sold, overview.units_sold)
        aovs = [item.average_order_value for item in all_rows.items]
        self.assertEqual(aovs, sorted(aovs))


if __name__ == "__main__":
    unittest.main()
