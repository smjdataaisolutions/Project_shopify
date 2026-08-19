import unittest
from datetime import date

from sqlalchemy.dialects import postgresql

from app.repositories.products_repository import ProductFilters, ProductsRepository


def sql_for(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class ProductsRepositoryTests(unittest.TestCase):
    def test_catalog_counts_products_and_variants_independently(self):
        sql = sql_for(ProductsRepository._catalog_counts_statement(ProductFilters()))

        self.assertIn("count(distinct(anon_", sql.lower())
        self.assertIn("count(distinct(product_variants.id))", sql.lower())

    def test_sales_scope_uses_current_products_positive_units_and_all_time_orders(self):
        eligible = ProductsRepository._eligible_sales(ProductFilters())
        sql = sql_for(eligible.select())

        self.assertIn("JOIN orders", sql)
        self.assertIn("JOIN products", sql)
        self.assertNotIn("product_variants", sql)
        self.assertIn("order_line_items.quantity > 0", sql)
        self.assertIn("orders.processed_at IS NOT NULL", sql)
        self.assertNotIn("orders.processed_at >=", sql)
        self.assertNotIn("orders.processed_at <", sql)

    def test_product_sales_aggregate_parent_products_and_reuse_line_revenue(self):
        eligible = ProductsRepository._eligible_sales(ProductFilters())
        product_sales = ProductsRepository._product_sales(eligible)
        summary = ProductsRepository._sales_summary_statement(product_sales)
        top = ProductsRepository._top_product_statement(product_sales)
        aggregate_sql = sql_for(product_sales.select())
        summary_sql = sql_for(summary)
        top_sql = sql_for(top)

        self.assertIn("GROUP BY", aggregate_sql)
        self.assertIn("unit_price", aggregate_sql)
        self.assertIn("quantity", aggregate_sql)
        self.assertIn("image_url", aggregate_sql)
        self.assertIn("count(", summary_sql.lower())
        self.assertIn("group by", summary_sql.lower())
        self.assertIn("ORDER BY", top_sql)
        self.assertIn("units_sold DESC", top_sql)
        self.assertIn("product_revenue DESC", top_sql)
        self.assertIn("product_id ASC", top_sql)
        self.assertIn("LIMIT 1", top_sql)

    def test_all_filters_scope_catalog_and_sales_queries(self):
        filters = ProductFilters(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 19),
            product_types=("Snowboard",),
            vendors=("Snowdevil",),
            statuses=("active", "archived"),
        )
        catalog_sql = sql_for(ProductsRepository._catalog_counts_statement(filters))
        sales_sql = sql_for(ProductsRepository._eligible_sales(filters).select())

        for sql in (catalog_sql, sales_sql):
            self.assertIn("products.product_type IN ('Snowboard')", sql)
            self.assertIn("products.vendor IN ('Snowdevil')", sql)
            self.assertIn("lower(products.status) IN ('active', 'archived')", sql)
        self.assertIn("orders.processed_at >= '2026-08-01'", sales_sql)
        self.assertIn("orders.processed_at < '2026-08-20'", sales_sql)

    def test_sales_performance_limits_and_orders_positive_product_units(self):
        eligible = ProductsRepository._eligible_sales(ProductFilters())
        product_sales = ProductsRepository._product_sales(eligible)
        top_sql = sql_for(
            ProductsRepository._ranked_product_units_statement(
                product_sales, descending=True
            )
        )
        low_sql = sql_for(
            ProductsRepository._ranked_product_units_statement(
                product_sales, descending=False
            )
        )

        for sql in (top_sql, low_sql):
            self.assertIn("units_sold > 0", sql)
            self.assertIn("LIMIT 10", sql)
            self.assertIn("product_id ASC", sql)
        self.assertIn("units_sold DESC", top_sql)
        self.assertIn("units_sold ASC", low_sql)

    def test_sales_performance_revenue_queries_aggregate_and_rank_in_postgresql(self):
        eligible = ProductsRepository._eligible_sales(ProductFilters())
        product_sales = ProductsRepository._product_sales(eligible)
        vendor_sql = sql_for(
            ProductsRepository._dimension_revenue_statement(eligible, "vendor")
        )
        product_type_sql = sql_for(
            ProductsRepository._dimension_revenue_statement(
                eligible, "product_type"
            )
        )
        product_sql = sql_for(
            ProductsRepository._product_revenue_statement(product_sales)
        )
        currency_sql = sql_for(
            ProductsRepository._sales_currency_statement(eligible)
        )

        for sql in (vendor_sql, product_type_sql, product_sql):
            self.assertIn("revenue DESC", sql)
            self.assertIn("LIMIT 10", sql)
            self.assertIn(" > 0", sql)
        self.assertIn("products.vendor", vendor_sql)
        self.assertIn("products.product_type", product_type_sql)
        self.assertIn("product_revenue", product_sql)
        self.assertIn("count(distinct", currency_sql.lower())

    def test_performance_table_starts_from_products_and_paginates_ranked_rows(self):
        filters = ProductFilters(vendors=("Acme",))
        eligible = ProductsRepository._eligible_sales(filters)
        sales = ProductsRepository._product_sales(eligible)
        base = ProductsRepository._performance_base_statement(
            filters,
            sales,
            "50%_off",
        ).subquery()
        ranked = ProductsRepository._performance_ranked_statement(base).subquery()
        sql = sql_for(
            ProductsRepository._performance_page_statement(
                ranked,
                page=2,
                page_size=10,
                sort_by="units_sold",
                sort_direction="desc",
                reporting_days=30,
            )
        )
        base_sql = sql_for(base.select())

        self.assertIn("FROM products", base_sql)
        self.assertIn("LEFT OUTER JOIN", base_sql)
        self.assertIn("inventory", base_sql)
        self.assertIn("products.vendor IN ('Acme')", base_sql)
        self.assertIn("ILIKE", base_sql)
        self.assertIn("ESCAPE", base_sql)
        self.assertIn("percent_rank() OVER", sql)
        self.assertIn("units_sold DESC", sql)
        self.assertIn("LIMIT 10", sql)
        self.assertIn("OFFSET 10", sql)


if __name__ == "__main__":
    unittest.main()
