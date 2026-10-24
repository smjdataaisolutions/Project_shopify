import importlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch


class ShopifyFullSyncSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        environment = {
            "SHOPIFY_STORE": "test-store-martina.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test-token",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }
        with patch.dict(os.environ, environment, clear=False):
            sys.modules.pop("job_conf.shpfy_postgre", None)
            cls.sync = importlib.import_module("job_conf.shpfy_postgre")

    def run_main(self, apply_ddl=None):
        cursor = MagicMock()
        cursor_context = MagicMock()
        cursor_context.__enter__.return_value = cursor
        connection = MagicMock()
        connection.cursor.return_value = cursor_context
        connection_context = MagicMock()
        connection_context.__enter__.return_value = connection

        environment = {}
        if apply_ddl is not None:
            environment["SHOPIFY_APPLY_SCHEMA_DDL"] = apply_ddl

        with (
            patch.dict(os.environ, environment, clear=False),
            patch.object(self.sync.psycopg, "connect", return_value=connection_context),
            patch.object(self.sync, "sync_products"),
            patch.object(self.sync, "sync_variants"),
            patch.object(self.sync, "sync_locations"),
            patch.object(self.sync, "sync_inventory"),
            patch.object(self.sync, "sync_orders"),
        ):
            if apply_ddl is None:
                os.environ.pop("SHOPIFY_APPLY_SCHEMA_DDL", None)
            self.sync.main()

        return cursor

    def test_schema_ddl_is_disabled_by_default(self):
        cursor = self.run_main()
        executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertNotIn(self.sync.LEGACY_SINGLE_TENANT_DDL, executed_sql)

    def test_legacy_schema_flag_cannot_enable_runtime_ddl(self):
        cursor = self.run_main("true")
        executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertNotIn(self.sync.LEGACY_SINGLE_TENANT_DDL, executed_sql)


if __name__ == "__main__":
    unittest.main()
