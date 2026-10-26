"""Validate configured PostgreSQL connectivity without changing data or schema."""

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import engine


TABLES = (
    "products",
    "product_variants",
    "locations",
    "inventory",
    "orders",
    "order_line_items",
    "shopify_sync_state",
)


def main() -> None:
    url = make_url(get_settings().database_url)
    print(f"Configured DB host: {url.host}")
    print(f"Configured database: {url.database}")
    print(f"TLS mode: {url.query.get('sslmode', 'not specified')}")

    with engine.connect() as connection:
        probe = connection.execute(text("SELECT 1")).scalar_one()
        print(f"Database SELECT 1: {probe}")
        print("Table counts:")
        for table in TABLES:
            count = connection.execute(
                text(f'SELECT COUNT(*) FROM "{table}"')
            ).scalar_one()
            print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
