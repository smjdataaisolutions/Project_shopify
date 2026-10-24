"""Read-only verification for an MT-001 analytics database migration."""

import argparse
import json
import os

import psycopg


TABLES = (
    "products", "product_variants", "locations", "inventory",
    "orders", "order_line_items", "shopify_sync_state",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url-env", default="MT_MIGRATION_DATABASE_URL")
    parser.add_argument("--expected-database", required=True)
    args = parser.parse_args()
    raw_url = os.environ.get(args.database_url_env, "").strip()
    if not raw_url:
        raise SystemExit(f"{args.database_url_env} is required.")
    url = raw_url.replace("postgresql+psycopg://", "postgresql://", 1)
    result = {"database": args.expected_database, "shops": [], "counts": {}, "checks": {}}
    with psycopg.connect(url) as connection:
        connection.read_only = True
        actual = connection.execute("SELECT current_database()").fetchone()[0]
        if actual != args.expected_database:
            raise SystemExit(
                f"Database mismatch: expected {args.expected_database!r}, got {actual!r}."
            )
        result["shops"] = connection.execute(
            "SELECT id, shop_domain, status, sync_status FROM shops ORDER BY id"
        ).fetchall()
        for table in TABLES:
            result["counts"][table] = connection.execute(
                f"SELECT shop_id, count(*) FROM {table} GROUP BY shop_id ORDER BY shop_id"
            ).fetchall()
        result["checks"]["variant_without_product"] = connection.execute(
            "SELECT count(*) FROM product_variants v LEFT JOIN products p "
            "ON p.shop_id=v.shop_id AND p.id=v.product_id "
            "WHERE v.product_id IS NOT NULL AND p.id IS NULL"
        ).fetchone()[0]
        result["checks"]["line_without_order"] = connection.execute(
            "SELECT count(*) FROM order_line_items li LEFT JOIN orders o "
            "ON o.shop_id=li.shop_id AND o.id=li.order_id "
            "WHERE li.order_id IS NOT NULL AND o.id IS NULL"
        ).fetchone()[0]
        result["checks"]["inventory_without_location"] = connection.execute(
            "SELECT count(*) FROM inventory i LEFT JOIN locations l "
            "ON l.shop_id=i.shop_id AND l.id=i.location_id WHERE l.id IS NULL"
        ).fetchone()[0]
        result["checks"]["null_tenant_rows"] = sum(
            connection.execute(
                f"SELECT count(*) FROM {table} WHERE shop_id IS NULL"
            ).fetchone()[0]
            for table in TABLES
        )
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
