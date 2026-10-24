import os
import unittest
from uuid import uuid4

from sqlalchemy import func, select, text


RUN_INTEGRATION = os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(RUN_INTEGRATION, "PostgreSQL tenant integration tests are opt-in")
class TenantIsolationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core.tenant import TenantPrincipal
        from app.db.models import (
            InventoryLevel,
            Location,
            Order,
            OrderLineItem,
            Product,
            ProductVariant,
            Shop,
            ShopifySyncState,
        )
        from app.db.session import SessionLocal
        from app.db.tenant_session import (
            TenantScopeError,
            TenantSessionLocal,
            register_or_get_tenant,
        )

        cls.models = (
            Product,
            ProductVariant,
            Location,
            InventoryLevel,
            Order,
            OrderLineItem,
            ShopifySyncState,
        )
        cls.Product = Product
        cls.Order = Order
        cls.OrderLineItem = OrderLineItem
        cls.SessionLocal = SessionLocal
        cls.TenantSessionLocal = TenantSessionLocal
        cls.TenantScopeError = TenantScopeError
        cls.register = register_or_get_tenant
        suffix = uuid4().hex[:10]
        cls.shop_a = f"fashion-{suffix}.myshopify.com"
        cls.shop_b = f"beauty-{suffix}.myshopify.com"
        cls.shop_empty = f"empty-{suffix}.myshopify.com"
        cls.product_id = "gid://shopify/Product/777777"
        cls.variant_id = "gid://shopify/ProductVariant/777777"
        cls.location_id = "gid://shopify/Location/777777"
        cls.item_id = "gid://shopify/InventoryItem/777777"
        cls.order_id = "gid://shopify/Order/777777"
        cls.line_id = "gid://shopify/LineItem/777777"

        cls.tenant_a = cls.register(TenantPrincipal(cls.shop_a, "user-a"))
        cls.tenant_b = cls.register(TenantPrincipal(cls.shop_b, "user-b"))
        cls.empty_tenant = cls.register(TenantPrincipal(cls.shop_empty, "user-empty"))
        cls.tenant_a_repeat = cls.register(TenantPrincipal(cls.shop_a, "user-a"))

        with SessionLocal.begin() as db:
            for tenant, label in ((cls.tenant_a, "Fashion"), (cls.tenant_b, "Beauty")):
                values = {"shop_id": tenant.shop_id}
                db.execute(text("INSERT INTO products (shop_id,id,title) VALUES (:shop_id,:id,:title)"), values | {"id": cls.product_id, "title": f"{label} Product"})
                db.execute(text("INSERT INTO product_variants (shop_id,id,product_id,title,inventory_item_id) VALUES (:shop_id,:id,:product_id,:title,:item_id)"), values | {"id": cls.variant_id, "product_id": cls.product_id, "title": f"{label} Variant", "item_id": cls.item_id})
                db.execute(text("INSERT INTO locations (shop_id,id,name) VALUES (:shop_id,:id,:name)"), values | {"id": cls.location_id, "name": f"{label} Location"})
                db.execute(text("INSERT INTO inventory (shop_id,inventory_item_id,location_id,location_name,quantities) VALUES (:shop_id,:item_id,:location_id,:name,'[]'::jsonb)"), values | {"item_id": cls.item_id, "location_id": cls.location_id, "name": f"{label} Location"})
                db.execute(text("INSERT INTO orders (shop_id,id,name,created_at,processed_at,currency_code,financial_status,fulfillment_status,total_price) VALUES (:shop_id,:id,:name,clock_timestamp(),clock_timestamp(),'USD','PAID','FULFILLED',:total)"), values | {"id": cls.order_id, "name": f"{label} Order", "total": 100})
                db.execute(text("INSERT INTO order_line_items (shop_id,id,order_id,product_id,variant_id,title,quantity,unit_price) VALUES (:shop_id,:id,:order_id,:product_id,:variant_id,:title,1,100)"), values | {"id": cls.line_id, "order_id": cls.order_id, "product_id": cls.product_id, "variant_id": cls.variant_id, "title": f"{label} Line"})
                db.execute(text("INSERT INTO shopify_sync_state (shop_id,source,last_successful_sync_at) VALUES (:shop_id,'shopify',clock_timestamp())"), values)

    def tenant_session(self, tenant):
        return self.TenantSessionLocal(info={"shop_id": tenant.shop_id})

    def test_registration_is_idempotent_and_new_shop_is_empty(self):
        self.assertEqual(self.tenant_a.shop_id, self.tenant_a_repeat.shop_id)
        with self.tenant_session(self.empty_tenant) as db:
            for model in self.models:
                self.assertEqual(db.scalar(select(func.count()).select_from(model)), 0)

    def test_all_seven_tables_are_isolated_with_reused_resource_ids(self):
        for tenant, expected_label in (
            (self.tenant_a, "Fashion"),
            (self.tenant_b, "Beauty"),
        ):
            with self.tenant_session(tenant) as db:
                for model in self.models:
                    self.assertEqual(db.scalar(select(func.count()).select_from(model)), 1)
                product = db.scalar(select(self.Product))
                order = db.scalar(select(self.Order))
                self.assertEqual(product.title, f"{expected_label} Product")
                self.assertEqual(order.name, f"{expected_label} Order")

    def test_join_cannot_cross_tenant_boundary(self):
        with self.SessionLocal.begin() as db:
            db.execute(
                text("DELETE FROM products WHERE shop_id=:shop_id AND id=:id"),
                {"shop_id": self.tenant_b.shop_id, "id": self.product_id},
            )
        with self.tenant_session(self.tenant_b) as db:
            rows = db.execute(
                select(self.OrderLineItem.id).join(
                    self.Product,
                    self.Product.id == self.OrderLineItem.product_id,
                )
            ).all()
            self.assertEqual(rows, [])

    def test_raw_sql_fails_closed_in_merchant_session(self):
        with self.tenant_session(self.tenant_a) as db:
            with self.assertRaises(self.TenantScopeError):
                db.execute(text("SELECT * FROM products"))

    def test_all_five_analytics_modules_execute_with_tenant_scope(self):
        from app.repositories.dashboard_repository import (
            DashboardRepository,
            OverviewFilters,
        )
        from app.repositories.inventory_repository import InventoryRepository
        from app.repositories.orders_repository import OrderFilters, OrdersRepository
        from app.repositories.products_repository import ProductFilters, ProductsRepository
        from app.repositories.sales_repository import SalesFilters, SalesRepository

        with self.tenant_session(self.tenant_a) as db:
            dashboard = DashboardRepository(db).get_dashboard_summary(
                OverviewFilters(), 10
            )
            products = ProductsRepository(db).get_kpi_inputs(ProductFilters())
            order_groups = OrdersRepository(db).get_kpi_aggregates(OrderFilters())
            sales = SalesRepository(db).get_sales_metrics(SalesFilters())
            inventory = InventoryRepository(db).get_filter_options()

        self.assertEqual(dashboard.total_products, 1)
        self.assertEqual(dashboard.total_orders, 1)
        self.assertEqual(products.catalog.total_products, 1)
        self.assertEqual(sum(group.orders_count for group in order_groups), 1)
        self.assertEqual(sales.orders_count, 1)
        self.assertEqual(len(inventory.locations), 1)

    def test_webhook_upsert_and_delete_cannot_touch_other_tenant(self):
        from app.services.shopify_webhook_sync import apply_shopify_webhook

        with self.SessionLocal.begin() as db:
            apply_shopify_webhook(
                db,
                shop_id=self.tenant_a.shop_id,
                topic="orders/updated",
                payload={"id": 777777, "name": "Fashion Updated", "line_items": []},
            )
        with self.SessionLocal() as db:
            rows = db.execute(
                text("SELECT shop_id,name FROM orders WHERE id=:id ORDER BY shop_id"),
                {"id": self.order_id},
            ).all()
        self.assertEqual(dict(rows)[self.tenant_a.shop_id], "Fashion Updated")
        self.assertEqual(dict(rows)[self.tenant_b.shop_id], "Beauty Order")

        with self.SessionLocal.begin() as db:
            apply_shopify_webhook(
                db,
                shop_id=self.tenant_a.shop_id,
                topic="orders/delete",
                payload={"id": 777777},
            )
        with self.SessionLocal() as db:
            remaining = dict(
                db.execute(
                    select(self.Order.shop_id, func.count())
                    .where(self.Order.id == self.order_id)
                    .group_by(self.Order.shop_id)
                ).all()
            )
        self.assertNotIn(self.tenant_a.shop_id, remaining)
        self.assertEqual(remaining[self.tenant_b.shop_id], 1)


if __name__ == "__main__":
    unittest.main()
