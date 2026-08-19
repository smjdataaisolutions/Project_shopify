import os
import unittest

from sqlalchemy import text

from app.db.session import SessionLocal
from app.repositories.products_repository import ProductFilters, ProductsRepository
from app.services.products_service import ProductsService


@unittest.skipUnless(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1",
    "Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test the configured PostgreSQL database.",
)
class ProductsPostgresTests(unittest.TestCase):
    def test_configured_postgresql_returns_consistent_product_kpis(self):
        with SessionLocal() as db:
            response = ProductsService(ProductsRepository(db)).get_kpis(
                ProductFilters(statuses=("active", "archived"))
            )

        self.assertGreaterEqual(response.total_products, 0)
        self.assertGreaterEqual(response.total_variants, 0)
        self.assertGreaterEqual(response.products_with_no_sales, 0)
        self.assertLessEqual(response.products_with_no_sales, response.total_products)
        if response.top_selling_product:
            self.assertGreater(response.top_selling_product.units_sold, 0)
        self.assertTrue(response.filter_options.statuses)

    def test_configured_postgresql_returns_ranked_product_sales(self):
        with SessionLocal() as db:
            response = ProductsService(ProductsRepository(db)).get_sales_performance(
                ProductFilters()
            )

            base_sql = """
                SELECT oli.product_id, SUM(oli.quantity)::bigint AS units_sold
                FROM order_line_items AS oli
                JOIN orders AS o ON o.id = oli.order_id
                JOIN products AS p ON p.id = oli.product_id
                WHERE o.processed_at IS NOT NULL
                  AND oli.product_id IS NOT NULL
                  AND oli.quantity > 0
                GROUP BY oli.product_id
                HAVING SUM(oli.quantity) > 0
            """
            expected_top = db.execute(
                text(base_sql + " ORDER BY units_sold DESC, oli.product_id ASC LIMIT 10")
            ).all()
            expected_low = db.execute(
                text(base_sql + " ORDER BY units_sold ASC, oli.product_id ASC LIMIT 10")
            ).all()

        self.assertLessEqual(len(response.top_selling), 10)
        self.assertLessEqual(len(response.low_selling), 10)
        self.assertEqual(
            [item.units_sold for item in response.top_selling],
            sorted(
                [item.units_sold for item in response.top_selling], reverse=True
            ),
        )
        self.assertEqual(
            [item.units_sold for item in response.low_selling],
            sorted(item.units_sold for item in response.low_selling),
        )
        self.assertTrue(all(item.units_sold > 0 for item in response.low_selling))
        for ranking in (
            response.sales_by_vendor,
            response.sales_by_product_type,
            response.product_revenue_contribution,
        ):
            self.assertLessEqual(len(ranking), 10)
            self.assertEqual(
                [item.revenue for item in ranking],
                sorted([item.revenue for item in ranking], reverse=True),
            )
            self.assertTrue(all(item.revenue > 0 for item in ranking))
        self.assertEqual(
            [(item.product_id, item.units_sold) for item in response.top_selling],
            [(row.product_id, row.units_sold) for row in expected_top],
        )
        self.assertEqual(
            [(item.product_id, item.units_sold) for item in response.low_selling],
            [(row.product_id, row.units_sold) for row in expected_low],
        )

        with SessionLocal() as db:
            revenue_sql = """
                SELECT oli.product_id,
                       SUM(COALESCE(oli.unit_price, 0) * oli.quantity) AS revenue
                FROM order_line_items AS oli
                JOIN orders AS o ON o.id = oli.order_id
                JOIN products AS p ON p.id = oli.product_id
                WHERE o.processed_at IS NOT NULL
                  AND oli.product_id IS NOT NULL
                  AND oli.quantity > 0
                GROUP BY oli.product_id
                HAVING SUM(COALESCE(oli.unit_price, 0) * oli.quantity) > 0
                ORDER BY revenue DESC, oli.product_id ASC
                LIMIT 10
            """
            expected_revenue = db.execute(text(revenue_sql)).all()

        self.assertEqual(
            [
                (item.product_id, item.revenue)
                for item in response.product_revenue_contribution
            ],
            [(row.product_id, row.revenue) for row in expected_revenue],
        )

    def test_configured_postgresql_returns_product_performance_table(self):
        with SessionLocal() as db:
            response = ProductsService(ProductsRepository(db)).get_performance_table(
                ProductFilters(),
                page=1,
                page_size=10,
                search="",
                sort_by="units_sold",
                sort_direction="desc",
            )
            expected = db.execute(
                text(
                    """
                    SELECT p.id AS product_id,
                           COALESCE(SUM(oli.quantity), 0)::bigint AS units_sold,
                           COALESCE(SUM(COALESCE(oli.unit_price, 0) * oli.quantity), 0) AS revenue,
                           COUNT(DISTINCT oli.order_id)::bigint AS orders
                    FROM products AS p
                    LEFT JOIN order_line_items AS oli
                      ON oli.product_id = p.id AND oli.quantity > 0
                    LEFT JOIN orders AS o
                      ON o.id = oli.order_id AND o.processed_at IS NOT NULL
                    WHERE o.id IS NOT NULL OR oli.id IS NULL
                    GROUP BY p.id
                    ORDER BY units_sold DESC, p.id ASC
                    LIMIT 1
                    """
                )
            ).first()

        self.assertGreaterEqual(response.reporting_days, 1)
        self.assertLessEqual(len(response.items), 10)
        self.assertEqual(response.pagination.page_size, 10)
        self.assertEqual(
            [item.units_sold for item in response.items],
            sorted([item.units_sold for item in response.items], reverse=True),
        )
        self.assertTrue(
            all(
                item.performance
                in {"top_seller", "healthy", "slow_moving", "no_sales"}
                for item in response.items
            )
        )
        if expected and response.items:
            item = response.items[0]
            self.assertEqual(item.product_id, expected.product_id)
            self.assertEqual(item.units_sold, expected.units_sold)
            self.assertEqual(item.revenue, expected.revenue)
            self.assertEqual(item.orders, expected.orders)


if __name__ == "__main__":
    unittest.main()
