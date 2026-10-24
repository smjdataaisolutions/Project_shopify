"""Run a data-only Shopify reconciliation using the persistent offline session."""

import importlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


REQUIRED_SCOPES = {"read_inventory", "read_locations", "read_orders", "write_products"}
TABLES = (
    "products",
    "product_variants",
    "inventory",
    "locations",
    "orders",
    "order_line_items",
    "shopify_sync_state",
)


def tenant_id(database_url, shop):
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "SELECT id FROM shops WHERE shop_domain = %s AND status = 'active'",
            (shop,),
        ).fetchone()
    if not row:
        raise RuntimeError(f"No active analytics tenant exists for {shop}.")
    return row[0]


def table_counts(database_url, shop_id):
    with psycopg.connect(database_url) as connection:
        counts = {
            table: connection.execute(
                f"SELECT count(*) FROM {table} WHERE shop_id = %s", (shop_id,)
            ).fetchone()[0]
            for table in TABLES
        }
        latest_order = connection.execute(
            "SELECT max(created_at) FROM orders WHERE shop_id = %s",
            (shop_id,),
        ).fetchone()[0]
        sync_time = connection.execute(
            """
            SELECT last_successful_sync_at
            FROM shopify_sync_state
            WHERE shop_id = %s AND source = 'shopify'
            """
            ,
            (shop_id,),
        ).fetchone()
    return counts, latest_order, sync_time[0] if sync_time else None


def load_offline_session(session_database_url, shop):
    with psycopg.connect(session_database_url) as connection:
        row = connection.execute(
            """
            SELECT "accessToken", scope, expires
            FROM "Session"
            WHERE shop = %s AND "isOnline" = false
            ORDER BY expires DESC NULLS FIRST
            LIMIT 1
            """,
            (shop,),
        ).fetchone()

    if not row:
        raise RuntimeError(f"No offline Shopify session exists for {shop}.")

    access_token, scope_value, expires = row
    granted_scopes = set((scope_value or "").split(","))
    missing_scopes = REQUIRED_SCOPES - granted_scopes
    if missing_scopes:
        raise RuntimeError(
            "Shopify session is missing required scopes: "
            + ", ".join(sorted(missing_scopes))
        )
    if expires is not None:
        comparable_expiry = expires
        if comparable_expiry.tzinfo is None:
            comparable_expiry = comparable_expiry.replace(tzinfo=timezone.utc)
        if comparable_expiry <= datetime.now(timezone.utc):
            raise RuntimeError("The Shopify offline access token has expired.")

    return access_token


def main():
    analytics_database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    session_database_url = os.environ["SHOPIFY_SESSION_DATABASE_URL"]
    shop = os.environ["SHOPIFY_STORE"].strip().lower()
    if not shop.endswith(".myshopify.com"):
        raise RuntimeError("SHOPIFY_STORE must be a canonical .myshopify.com domain.")
    if analytics_database_url == session_database_url:
        raise RuntimeError("Analytics and Shopify session databases must be separate.")

    shop_id = tenant_id(analytics_database_url, shop)
    access_token = load_offline_session(session_database_url, shop)
    before_counts, before_latest_order, before_sync_time = table_counts(
        analytics_database_url, shop_id
    )

    os.environ["SHOPIFY_ACCESS_TOKEN"] = access_token
    os.environ["DATABASE_URL"] = analytics_database_url
    sync = importlib.import_module("job_conf.shpfy_postgre")
    sync.main()

    after_counts, after_latest_order, after_sync_time = table_counts(
        analytics_database_url, shop_id
    )
    print(f"shop={shop}")
    for table in TABLES:
        print(f"{table}: {before_counts[table]} -> {after_counts[table]}")
    print(f"latest_order_created_at: {before_latest_order} -> {after_latest_order}")
    print(f"last_successful_sync_at: {before_sync_time} -> {after_sync_time}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        message = str(error)
        for variable in ("DATABASE_URL", "SHOPIFY_SESSION_DATABASE_URL"):
            secret = os.getenv(variable)
            if secret:
                message = message.replace(secret, "[REDACTED]")
                message = message.replace(
                    secret.replace("postgresql+psycopg://", "postgresql://", 1),
                    "[REDACTED]",
                )
        print(
            f"Reconciliation failed: {type(error).__name__}: {message}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
