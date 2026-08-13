

import os
from decimal import Decimal

import psycopg
import requests
from psycopg.types.json import Jsonb


STORE = os.environ["SHOPIFY_STORE"]
TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]
API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-10")
DATABASE_URL = os.environ["DATABASE_URL"]
PAGE_SIZE = 100

GRAPHQL_URL = f"https://{STORE}/admin/api/{API_VERSION}/graphql.json"

PRODUCTS_QUERY = """
query Products($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    nodes { id title handle status vendor productType tags createdAt updatedAt }
    pageInfo { hasNextPage endCursor }
  }
}
"""

VARIANTS_QUERY = """
query ProductVariants($first: Int!, $after: String) {
  productVariants(first: $first, after: $after) {
    nodes {
      id title sku barcode price inventoryPolicy inventoryQuantity
      product { id }
      inventoryItem { id sku tracked }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

INVENTORY_QUERY = """
query InventoryItems($first: Int!, $after: String) {
  inventoryItems(first: $first, after: $after) {
    nodes {
      id sku tracked requiresShipping updatedAt
      inventoryLevels(first: 250) {
        nodes {
          location { id name }
          quantities(names: ["available", "committed", "incoming", "on_hand", "reserved"]) {
            name
            quantity
          }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

LOCATIONS_QUERY = """
query Locations($first: Int!, $after: String) {
  locations(first: $first, after: $after, includeInactive: true) {
    nodes {
      id name isActive fulfillsOnlineOrders hasActiveInventory
      address { address1 address2 city province country zip }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

# Customer and Customer PII fields are intentionally excluded.
ORDERS_QUERY = """
query Orders($first: Int!, $after: String) {
  orders(first: $first, after: $after, sortKey: PROCESSED_AT, reverse: true) {
    nodes {
      id
      name
      createdAt
      processedAt
      cancelledAt
      currencyCode
      displayFinancialStatus
      displayFulfillmentStatus
      sourceName
      subtotalPriceSet { shopMoney { amount } }
      totalDiscountsSet { shopMoney { amount } }
      totalShippingPriceSet { shopMoney { amount } }
      totalTaxSet { shopMoney { amount } }
      totalPriceSet { shopMoney { amount } }
      totalRefundedSet { shopMoney { amount } }
      refunds {
        createdAt
        note
      }
      lineItems(first: 250) {
        nodes {
          id
          title
          sku
          quantity
          currentQuantity
          fulfillableQuantity
          originalUnitPriceSet { shopMoney { amount currencyCode } }
          variant { id product { id } }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

DDL = """
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY, title TEXT, handle TEXT, status TEXT, vendor TEXT,
  product_type TEXT, tags JSONB, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS product_variants (
  id TEXT PRIMARY KEY, product_id TEXT, title TEXT, sku TEXT, barcode TEXT,
  price NUMERIC, inventory_policy TEXT, inventory_quantity INTEGER,
  inventory_item_id TEXT, inventory_tracked BOOLEAN
);

CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY, name TEXT, is_active BOOLEAN,
  fulfills_online_orders BOOLEAN, has_active_inventory BOOLEAN, address JSONB
);

CREATE TABLE IF NOT EXISTS inventory (
  inventory_item_id TEXT NOT NULL, location_id TEXT NOT NULL, location_name TEXT,
  sku TEXT, tracked BOOLEAN, requires_shipping BOOLEAN, quantities JSONB,
  updated_at TIMESTAMPTZ,
  PRIMARY KEY (inventory_item_id, location_id)
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY, name TEXT, created_at TIMESTAMPTZ, processed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ, refunded_at TIMESTAMPTZ,
  currency_code TEXT, financial_status TEXT, fulfillment_status TEXT,
  sales_channel TEXT,
  subtotal_price NUMERIC, total_discount NUMERIC, total_shipping NUMERIC,
  total_tax NUMERIC, total_price NUMERIC, total_refunded NUMERIC,
  refund_reason TEXT
);

CREATE TABLE IF NOT EXISTS shopify_sync_state (
  source TEXT PRIMARY KEY,
  last_successful_sync_at TIMESTAMPTZ NOT NULL
);

INSERT INTO shopify_sync_state (source, last_successful_sync_at)
SELECT 'shopify', MAX(updated_at)
FROM (
  SELECT updated_at FROM products
  UNION ALL
  SELECT updated_at FROM inventory
) AS synchronized_source_updates
HAVING MAX(updated_at) IS NOT NULL
ON CONFLICT (source) DO NOTHING;

ALTER TABLE orders ADD COLUMN IF NOT EXISTS subtotal_price NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_discount NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_shipping NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_tax NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_price NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS total_refunded NUMERIC;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_reason TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS sales_channel TEXT;

CREATE TABLE IF NOT EXISTS order_line_items (
  id TEXT PRIMARY KEY, order_id TEXT, product_id TEXT, variant_id TEXT,
  title TEXT, sku TEXT, quantity INTEGER, current_quantity INTEGER,
  fulfillable_quantity INTEGER, unit_price NUMERIC, currency_code TEXT
);
"""


def graphql(query, variables):
    response = requests.post(
        GRAPHQL_URL,
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN},
        json={"query": query, "variables": variables},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Shopify GraphQL errors: {payload['errors']}")
    return payload["data"]


def paginate(query, root_field):
    after = None
    while True:
        connection = graphql(query, {"first": PAGE_SIZE, "after": after})[root_field]
        yield from connection["nodes"]
        if not connection["pageInfo"]["hasNextPage"]:
            return
        after = connection["pageInfo"]["endCursor"]


def upsert(cursor, table, row, key_columns):
    columns = list(row)
    update_columns = [column for column in columns if column not in key_columns]
    sql = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join(["%s"] * len(columns))})
        ON CONFLICT ({", ".join(key_columns)}) DO UPDATE SET
        {", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)}
    """
    cursor.execute(sql, [row[column] for column in columns])


def sync_products(cursor):
    for product in paginate(PRODUCTS_QUERY, "products"):
        upsert(cursor, "products", {
            "id": product["id"], "title": product.get("title"),
            "handle": product.get("handle"), "status": product.get("status"),
            "vendor": product.get("vendor"), "product_type": product.get("productType"),
            "tags": Jsonb(product.get("tags", [])), "created_at": product.get("createdAt"),
            "updated_at": product.get("updatedAt"),
        }, ["id"])


def sync_variants(cursor):
    for variant in paginate(VARIANTS_QUERY, "productVariants"):
        product = variant.get("product") or {}
        item = variant.get("inventoryItem") or {}
        upsert(cursor, "product_variants", {
            "id": variant["id"], "product_id": product.get("id"),
            "title": variant.get("title"), "sku": variant.get("sku"),
            "barcode": variant.get("barcode"),
            "price": Decimal(variant["price"]) if variant.get("price") else None,
            "inventory_policy": variant.get("inventoryPolicy"),
            "inventory_quantity": variant.get("inventoryQuantity"),
            "inventory_item_id": item.get("id"), "inventory_tracked": item.get("tracked"),
        }, ["id"])


def sync_inventory(cursor):
    for item in paginate(INVENTORY_QUERY, "inventoryItems"):
        for level in item["inventoryLevels"]["nodes"]:
            location = level["location"]
            upsert(cursor, "inventory", {
                "inventory_item_id": item["id"], "location_id": location["id"],
                "location_name": location.get("name"), "sku": item.get("sku"),
                "tracked": item.get("tracked"), "requires_shipping": item.get("requiresShipping"),
                "quantities": Jsonb(level.get("quantities", [])), "updated_at": item.get("updatedAt"),
            }, ["inventory_item_id", "location_id"])


def sync_locations(cursor):
    for location in paginate(LOCATIONS_QUERY, "locations"):
        upsert(cursor, "locations", {
            "id": location["id"], "name": location.get("name"),
            "is_active": location.get("isActive"),
            "fulfills_online_orders": location.get("fulfillsOnlineOrders"),
            "has_active_inventory": location.get("hasActiveInventory"),
            "address": Jsonb(location["address"]) if location.get("address") else None,
        }, ["id"])


def sync_orders(cursor):
    for order in paginate(ORDERS_QUERY, "orders"):
        def shop_money_amount(field_name):
            money = (order.get(field_name) or {}).get("shopMoney") or {}
            return Decimal(money["amount"]) if money.get("amount") is not None else None

        refunds = order.get("refunds") or []
        refund_dates = [
            refund["createdAt"] for refund in refunds if refund.get("createdAt")
        ]
        refund_notes = list(dict.fromkeys(
            refund["note"].strip()
            for refund in refunds
            if refund.get("note") and refund["note"].strip()
        ))

        upsert(cursor, "orders", {
            "id": order["id"], "name": order.get("name"),
            "created_at": order.get("createdAt"), "processed_at": order.get("processedAt"),
            "cancelled_at": order.get("cancelledAt"),
            "refunded_at": max(refund_dates) if refund_dates else None,
            "currency_code": order.get("currencyCode"),
            "financial_status": order.get("displayFinancialStatus"),
            "fulfillment_status": order.get("displayFulfillmentStatus"),
            "sales_channel": order.get("sourceName"),
            "subtotal_price": shop_money_amount("subtotalPriceSet"),
            "total_discount": shop_money_amount("totalDiscountsSet"),
            "total_shipping": shop_money_amount("totalShippingPriceSet"),
            "total_tax": shop_money_amount("totalTaxSet"),
            "total_price": shop_money_amount("totalPriceSet"),
            "total_refunded": shop_money_amount("totalRefundedSet"),
            "refund_reason": " | ".join(refund_notes) or None,
        }, ["id"])

        for line in order["lineItems"]["nodes"]:
            variant = line.get("variant") or {}
            product = variant.get("product") or {}
            money = (line.get("originalUnitPriceSet") or {}).get("shopMoney") or {}
            upsert(cursor, "order_line_items", {
                "id": line["id"], "order_id": order["id"],
                "product_id": product.get("id"), "variant_id": variant.get("id"),
                "title": line.get("title"), "sku": line.get("sku"),
                "quantity": line.get("quantity"), "current_quantity": line.get("currentQuantity"),
                "fulfillable_quantity": line.get("fulfillableQuantity"),
                "unit_price": Decimal(money["amount"]) if money.get("amount") else None,
                "currency_code": money.get("currencyCode"),
            }, ["id"])


def main():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)
            sync_products(cursor)
            sync_variants(cursor)
            sync_locations(cursor)
            sync_inventory(cursor)
            sync_orders(cursor)
            cursor.execute(
                """
                INSERT INTO shopify_sync_state (source, last_successful_sync_at)
                VALUES ('shopify', clock_timestamp())
                ON CONFLICT (source) DO UPDATE SET
                  last_successful_sync_at = EXCLUDED.last_successful_sync_at
                """
            )
        conn.commit()
    print("Shopify non-PII data synchronized to PostgreSQL.")


if __name__ == "__main__":
    main()
