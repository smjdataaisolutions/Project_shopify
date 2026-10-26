import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


ALLOWED_WEBHOOK_TOPICS = frozenset(
    {
        "app/uninstalled",
        "inventory_items/create",
        "inventory_items/delete",
        "inventory_items/update",
        "inventory_levels/connect",
        "inventory_levels/disconnect",
        "inventory_levels/update",
        "locations/activate",
        "locations/create",
        "locations/deactivate",
        "locations/delete",
        "locations/update",
        "orders/create",
        "orders/delete",
        "orders/updated",
        "products/create",
        "products/delete",
        "products/update",
    }
)


class UnsupportedWebhookTopicError(ValueError):
    """Raised when a webhook topic is not explicitly supported."""


def _gid(resource: str, value: Any, explicit_gid: Any = None) -> str | None:
    if isinstance(explicit_gid, str) and explicit_gid.startswith("gid://shopify/"):
        return explicit_gid
    if value is None or value == "":
        return None
    value_string = str(value)
    if value_string.startswith("gid://shopify/"):
        return value_string
    return f"gid://shopify/{resource}/{value_string}"


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _money(payload: dict[str, Any], scalar_name: str, set_name: str) -> Decimal | None:
    money_set = payload.get(set_name) or {}
    shop_money = money_set.get("shop_money") or money_set.get("shopMoney") or {}
    return _decimal(shop_money.get("amount") or payload.get(scalar_name))


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def _sync_state(db: Session, shop_id: int) -> None:
    db.execute(
        text(
            """
            INSERT INTO shopify_sync_state (shop_id, source, last_successful_sync_at)
            VALUES (:shop_id, 'shopify', clock_timestamp())
            ON CONFLICT (shop_id, source) DO UPDATE SET
              last_successful_sync_at = EXCLUDED.last_successful_sync_at
            """
        ),
        {"shop_id": shop_id},
    )


def _product_id(payload: dict[str, Any]) -> str | None:
    return _gid("Product", payload.get("id"), payload.get("admin_graphql_api_id"))


def _variant_id(variant: dict[str, Any]) -> str | None:
    return _gid(
        "ProductVariant",
        variant.get("id"),
        variant.get("admin_graphql_api_id"),
    )


def _inventory_item_id(payload: dict[str, Any]) -> str | None:
    if payload.get("inventory_item_id") is not None:
        return _gid("InventoryItem", payload.get("inventory_item_id"))
    return _gid(
        "InventoryItem",
        payload.get("id"),
        payload.get("admin_graphql_api_id"),
    )


def _location_id(payload: dict[str, Any]) -> str | None:
    if payload.get("location_id") is not None:
        return _gid("Location", payload.get("location_id"))
    return _gid(
        "Location",
        payload.get("id"),
        payload.get("admin_graphql_api_id"),
    )


def _delete_inventory_items(db: Session, shop_id: int, item_ids: list[str]) -> None:
    for item_id in item_ids:
        db.execute(
            text(
                "DELETE FROM inventory "
                "WHERE shop_id = :shop_id AND inventory_item_id = :item_id"
            ),
            {"shop_id": shop_id, "item_id": item_id},
        )


def _sync_product(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    product_id = _product_id(payload)
    if not product_id:
        raise ValueError("Product webhook is missing an ID.")

    image = payload.get("image") or payload.get("featured_image") or {}
    raw_tags = payload.get("tags") or []
    tags = (
        [part.strip() for part in raw_tags.split(",") if part.strip()]
        if isinstance(raw_tags, str)
        else raw_tags
    )
    db.execute(
        text(
            """
            INSERT INTO products (
              shop_id, id, title, handle, status, vendor, product_type, image_url,
              tags, created_at, updated_at
            ) VALUES (
              :shop_id, :id, :title, :handle, :status, :vendor, :product_type, :image_url,
              CAST(:tags AS JSONB), :created_at, :updated_at
            )
            ON CONFLICT (shop_id, id) DO UPDATE SET
              title = EXCLUDED.title,
              handle = EXCLUDED.handle,
              status = EXCLUDED.status,
              vendor = EXCLUDED.vendor,
              product_type = EXCLUDED.product_type,
              image_url = EXCLUDED.image_url,
              tags = EXCLUDED.tags,
              created_at = EXCLUDED.created_at,
              updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "shop_id": shop_id,
            "id": product_id,
            "title": payload.get("title"),
            "handle": payload.get("handle"),
            "status": payload.get("status"),
            "vendor": payload.get("vendor"),
            "product_type": payload.get("product_type"),
            "image_url": image.get("src") or image.get("url"),
            "tags": _json(tags),
            "created_at": _timestamp(payload.get("created_at")),
            "updated_at": _timestamp(payload.get("updated_at")),
        },
    )

    variants = payload.get("variants") or []
    current_variant_ids: set[str] = set()
    for variant in variants:
        variant_id = _variant_id(variant)
        if not variant_id:
            continue
        current_variant_ids.add(variant_id)
        inventory_item_id = _gid(
            "InventoryItem",
            variant.get("inventory_item_id"),
            variant.get("inventory_item_admin_graphql_api_id"),
        )
        db.execute(
            text(
                """
                INSERT INTO product_variants (
                  shop_id, id, product_id, title, sku, barcode, price, inventory_policy,
                  inventory_quantity, inventory_item_id, inventory_tracked
                ) VALUES (
                  :shop_id, :id, :product_id, :title, :sku, :barcode, :price,
                  :inventory_policy, :inventory_quantity, :inventory_item_id,
                  :inventory_tracked
                )
                ON CONFLICT (shop_id, id) DO UPDATE SET
                  product_id = EXCLUDED.product_id,
                  title = EXCLUDED.title,
                  sku = EXCLUDED.sku,
                  barcode = EXCLUDED.barcode,
                  price = EXCLUDED.price,
                  inventory_policy = EXCLUDED.inventory_policy,
                  inventory_quantity = EXCLUDED.inventory_quantity,
                  inventory_item_id = EXCLUDED.inventory_item_id,
                  inventory_tracked = EXCLUDED.inventory_tracked
                """
            ),
            {
                "shop_id": shop_id,
                "id": variant_id,
                "product_id": product_id,
                "title": variant.get("title"),
                "sku": variant.get("sku"),
                "barcode": variant.get("barcode"),
                "price": _decimal(variant.get("price")),
                "inventory_policy": variant.get("inventory_policy"),
                "inventory_quantity": variant.get("inventory_quantity"),
                "inventory_item_id": inventory_item_id,
                "inventory_tracked": variant.get("inventory_management") is not None,
            },
        )

    complete_variant_ids = payload.get("variant_gids")
    if complete_variant_ids:
        current_variant_ids = {
            value.get("admin_graphql_api_id")
            for value in complete_variant_ids
            if isinstance(value, dict) and value.get("admin_graphql_api_id")
        }
    elif len(variants) >= 100:
        return

    existing = db.execute(
        text(
            "SELECT id, inventory_item_id FROM product_variants "
            "WHERE shop_id = :shop_id AND product_id = :id"
        ),
        {"shop_id": shop_id, "id": product_id},
    ).all()
    stale = [row for row in existing if row[0] not in current_variant_ids]
    _delete_inventory_items(db, shop_id, [row[1] for row in stale if row[1]])
    for variant_id, _ in stale:
        db.execute(
            text("DELETE FROM product_variants WHERE shop_id = :shop_id AND id = :id"),
            {"shop_id": shop_id, "id": variant_id},
        )


def _delete_product(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    product_id = _product_id(payload)
    if not product_id:
        raise ValueError("Product delete webhook is missing an ID.")
    item_ids = db.execute(
        text(
            "SELECT inventory_item_id FROM product_variants "
            "WHERE shop_id = :shop_id AND product_id = :id "
            "AND inventory_item_id IS NOT NULL"
        ),
        {"shop_id": shop_id, "id": product_id},
    ).scalars().all()
    _delete_inventory_items(db, shop_id, list(item_ids))
    db.execute(
        text(
            "DELETE FROM product_variants "
            "WHERE shop_id = :shop_id AND product_id = :id"
        ),
        {"shop_id": shop_id, "id": product_id},
    )
    db.execute(
        text("DELETE FROM products WHERE shop_id = :shop_id AND id = :id"),
        {"shop_id": shop_id, "id": product_id},
    )


def _sync_inventory_item(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    item_id = _inventory_item_id(payload)
    if not item_id:
        raise ValueError("Inventory item webhook is missing an ID.")
    db.execute(
        text(
            """
            UPDATE product_variants
            SET sku = COALESCE(:sku, sku), inventory_tracked = :tracked
            WHERE shop_id = :shop_id AND inventory_item_id = :item_id
            """
        ),
        {"shop_id": shop_id, "item_id": item_id, "sku": payload.get("sku"), "tracked": payload.get("tracked")},
    )
    db.execute(
        text(
            """
            UPDATE inventory
            SET sku = COALESCE(:sku, sku), tracked = :tracked,
                requires_shipping = :requires_shipping,
                updated_at = COALESCE(:updated_at, updated_at)
            WHERE shop_id = :shop_id AND inventory_item_id = :item_id
            """
        ),
        {
            "shop_id": shop_id,
            "item_id": item_id,
            "sku": payload.get("sku"),
            "tracked": payload.get("tracked"),
            "requires_shipping": payload.get("requires_shipping"),
            "updated_at": _timestamp(payload.get("updated_at")),
        },
    )


def _delete_inventory_item(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    item_id = _inventory_item_id(payload)
    if not item_id:
        raise ValueError("Inventory item delete webhook is missing an ID.")
    _delete_inventory_items(db, shop_id, [item_id])
    db.execute(
        text(
            """
            UPDATE product_variants
            SET inventory_item_id = NULL, inventory_tracked = NULL
            WHERE shop_id = :shop_id AND inventory_item_id = :item_id
            """
        ),
        {"shop_id": shop_id, "item_id": item_id},
    )


def _merge_available_quantity(existing: Any, available: Any) -> list[dict[str, Any]]:
    quantities = [dict(value) for value in (existing or []) if isinstance(value, dict)]
    for value in quantities:
        if value.get("name") == "available":
            value["quantity"] = available
            return quantities
    quantities.append({"name": "available", "quantity": available})
    return quantities


def _sync_inventory_level(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    item_id = _inventory_item_id(payload)
    location_id = _location_id(payload)
    if not item_id or not location_id:
        raise ValueError("Inventory-level webhook is missing an ID.")
    existing = db.execute(
        text(
            """
            SELECT quantities FROM inventory
            WHERE shop_id = :shop_id
              AND inventory_item_id = :item_id AND location_id = :location_id
            """
        ),
        {"shop_id": shop_id, "item_id": item_id, "location_id": location_id},
    ).scalar_one_or_none()
    metadata = db.execute(
        text(
            """
            SELECT l.name, v.sku, v.inventory_tracked
            FROM locations l
            LEFT JOIN product_variants v
              ON v.shop_id = l.shop_id AND v.inventory_item_id = :item_id
            WHERE l.shop_id = :shop_id AND l.id = :location_id
            LIMIT 1
            """
        ),
        {"shop_id": shop_id, "item_id": item_id, "location_id": location_id},
    ).first()
    quantities = _merge_available_quantity(existing, payload.get("available"))
    db.execute(
        text(
            """
            INSERT INTO inventory (
              shop_id, inventory_item_id, location_id, location_name, sku, tracked,
              requires_shipping, quantities, updated_at
            ) VALUES (
              :shop_id, :item_id, :location_id, :location_name, :sku, :tracked,
              NULL, CAST(:quantities AS JSONB), :updated_at
            )
            ON CONFLICT (shop_id, inventory_item_id, location_id) DO UPDATE SET
              location_name = COALESCE(EXCLUDED.location_name, inventory.location_name),
              sku = COALESCE(EXCLUDED.sku, inventory.sku),
              tracked = COALESCE(EXCLUDED.tracked, inventory.tracked),
              quantities = EXCLUDED.quantities,
              updated_at = COALESCE(EXCLUDED.updated_at, inventory.updated_at)
            """
        ),
        {
            "shop_id": shop_id,
            "item_id": item_id,
            "location_id": location_id,
            "location_name": metadata[0] if metadata else None,
            "sku": metadata[1] if metadata else None,
            "tracked": metadata[2] if metadata else None,
            "quantities": _json(quantities),
            "updated_at": _timestamp(payload.get("updated_at")),
        },
    )


def _delete_inventory_level(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    item_id = _inventory_item_id(payload)
    location_id = _location_id(payload)
    if not item_id or not location_id:
        raise ValueError("Inventory-level disconnect webhook is missing an ID.")
    db.execute(
        text(
            """
            DELETE FROM inventory
            WHERE shop_id = :shop_id
              AND inventory_item_id = :item_id AND location_id = :location_id
            """
        ),
        {"shop_id": shop_id, "item_id": item_id, "location_id": location_id},
    )


def _sync_location(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    location_id = _location_id(payload)
    if not location_id:
        raise ValueError("Location webhook is missing an ID.")
    address = payload.get("address")
    if not address:
        address = {
            key: payload.get(key)
            for key in ("address1", "address2", "city", "province", "country", "zip")
            if payload.get(key) is not None
        }
    is_active = payload.get("active", payload.get("is_active"))
    db.execute(
        text(
            """
            INSERT INTO locations (
              shop_id, id, name, is_active, fulfills_online_orders,
              has_active_inventory, address
            ) VALUES (
              :shop_id, :id, :name, :is_active, :fulfills_online_orders,
              :has_active_inventory, CAST(:address AS JSONB)
            )
            ON CONFLICT (shop_id, id) DO UPDATE SET
              name = EXCLUDED.name,
              is_active = COALESCE(EXCLUDED.is_active, locations.is_active),
              fulfills_online_orders = COALESCE(
                EXCLUDED.fulfills_online_orders, locations.fulfills_online_orders
              ),
              has_active_inventory = COALESCE(
                EXCLUDED.has_active_inventory, locations.has_active_inventory
              ),
              address = COALESCE(EXCLUDED.address, locations.address)
            """
        ),
        {
            "shop_id": shop_id,
            "id": location_id,
            "name": payload.get("name"),
            "is_active": is_active,
            "fulfills_online_orders": payload.get("fulfills_online_orders"),
            "has_active_inventory": payload.get("has_active_inventory"),
            "address": _json(address) if address else None,
        },
    )
    db.execute(
        text(
            "UPDATE inventory SET location_name = :name "
            "WHERE shop_id = :shop_id AND location_id = :id"
        ),
        {"shop_id": shop_id, "id": location_id, "name": payload.get("name")},
    )


def _delete_location(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    location_id = _location_id(payload)
    if not location_id:
        raise ValueError("Location delete webhook is missing an ID.")
    parameters = {"shop_id": shop_id, "id": location_id}
    db.execute(
        text("DELETE FROM inventory WHERE shop_id = :shop_id AND location_id = :id"),
        parameters,
    )
    db.execute(
        text("DELETE FROM locations WHERE shop_id = :shop_id AND id = :id"),
        parameters,
    )


def _order_refund_values(payload: dict[str, Any]) -> tuple[datetime | None, Decimal | None, str | None]:
    refunds = payload.get("refunds") or []
    dates = [
        value
        for value in (_timestamp(refund.get("created_at")) for refund in refunds)
        if value is not None
    ]
    notes = list(
        dict.fromkeys(
            refund.get("note", "").strip()
            for refund in refunds
            if isinstance(refund.get("note"), str) and refund.get("note", "").strip()
        )
    )
    total = Decimal("0")
    found_amount = False
    for refund in refunds:
        for transaction in refund.get("transactions") or []:
            if transaction.get("kind") == "refund" and transaction.get("status") == "success":
                amount = _decimal(transaction.get("amount"))
                if amount is not None:
                    total += amount
                    found_amount = True
    return (
        max(dates) if dates else None,
        total if found_amount else None,
        " | ".join(notes) or None,
    )


def _sync_order(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    order_id = _gid("Order", payload.get("id"), payload.get("admin_graphql_api_id"))
    if not order_id:
        raise ValueError("Order webhook is missing an ID.")
    refunded_at, total_refunded, refund_reason = _order_refund_values(payload)
    db.execute(
        text(
            """
            INSERT INTO orders (
              shop_id, id, name, created_at, processed_at, cancelled_at, refunded_at,
              currency_code, financial_status, fulfillment_status, sales_channel,
              subtotal_price, total_discount, total_shipping, total_tax,
              total_price, total_refunded, refund_reason
            ) VALUES (
              :shop_id, :id, :name, :created_at, :processed_at, :cancelled_at, :refunded_at,
              :currency_code, :financial_status, :fulfillment_status, :sales_channel,
              :subtotal_price, :total_discount, :total_shipping, :total_tax,
              :total_price, :total_refunded, :refund_reason
            )
            ON CONFLICT (shop_id, id) DO UPDATE SET
              name = EXCLUDED.name,
              created_at = EXCLUDED.created_at,
              processed_at = EXCLUDED.processed_at,
              cancelled_at = EXCLUDED.cancelled_at,
              refunded_at = COALESCE(EXCLUDED.refunded_at, orders.refunded_at),
              currency_code = EXCLUDED.currency_code,
              financial_status = EXCLUDED.financial_status,
              fulfillment_status = EXCLUDED.fulfillment_status,
              sales_channel = EXCLUDED.sales_channel,
              subtotal_price = EXCLUDED.subtotal_price,
              total_discount = EXCLUDED.total_discount,
              total_shipping = EXCLUDED.total_shipping,
              total_tax = EXCLUDED.total_tax,
              total_price = EXCLUDED.total_price,
              total_refunded = COALESCE(EXCLUDED.total_refunded, orders.total_refunded),
              refund_reason = COALESCE(EXCLUDED.refund_reason, orders.refund_reason)
            """
        ),
        {
            "shop_id": shop_id,
            "id": order_id,
            "name": payload.get("name"),
            "created_at": _timestamp(payload.get("created_at")),
            "processed_at": _timestamp(payload.get("processed_at")),
            "cancelled_at": _timestamp(payload.get("cancelled_at")),
            "refunded_at": refunded_at,
            "currency_code": payload.get("currency") or payload.get("currency_code"),
            "financial_status": payload.get("financial_status"),
            "fulfillment_status": payload.get("fulfillment_status"),
            "sales_channel": payload.get("source_name"),
            "subtotal_price": _money(payload, "subtotal_price", "subtotal_price_set"),
            "total_discount": _money(payload, "total_discounts", "total_discounts_set"),
            "total_shipping": _money(payload, "total_shipping_price", "total_shipping_price_set"),
            "total_tax": _money(payload, "total_tax", "total_tax_set"),
            "total_price": _money(payload, "total_price", "total_price_set"),
            "total_refunded": total_refunded,
            "refund_reason": refund_reason,
        },
    )

    current_line_ids: set[str] = set()
    for line in payload.get("line_items") or []:
        line_id = _gid("LineItem", line.get("id"), line.get("admin_graphql_api_id"))
        if not line_id:
            continue
        current_line_ids.add(line_id)
        unit_price = _money(line, "price", "price_set")
        db.execute(
            text(
                """
                INSERT INTO order_line_items (
                  shop_id, id, order_id, product_id, variant_id, title, sku, quantity,
                  current_quantity, fulfillable_quantity, unit_price, currency_code
                ) VALUES (
                  :shop_id, :id, :order_id, :product_id, :variant_id, :title, :sku, :quantity,
                  :current_quantity, :fulfillable_quantity, :unit_price, :currency_code
                )
                ON CONFLICT (shop_id, id) DO UPDATE SET
                  order_id = EXCLUDED.order_id,
                  product_id = EXCLUDED.product_id,
                  variant_id = EXCLUDED.variant_id,
                  title = EXCLUDED.title,
                  sku = EXCLUDED.sku,
                  quantity = EXCLUDED.quantity,
                  current_quantity = EXCLUDED.current_quantity,
                  fulfillable_quantity = EXCLUDED.fulfillable_quantity,
                  unit_price = EXCLUDED.unit_price,
                  currency_code = EXCLUDED.currency_code
                """
            ),
            {
                "shop_id": shop_id,
                "id": line_id,
                "order_id": order_id,
                "product_id": _gid("Product", line.get("product_id")),
                "variant_id": _gid("ProductVariant", line.get("variant_id")),
                "title": line.get("title"),
                "sku": line.get("sku"),
                "quantity": line.get("quantity"),
                "current_quantity": line.get("current_quantity"),
                "fulfillable_quantity": line.get("fulfillable_quantity"),
                "unit_price": unit_price,
                "currency_code": payload.get("currency") or payload.get("currency_code"),
            },
        )

    existing_line_ids = db.execute(
        text(
            "SELECT id FROM order_line_items "
            "WHERE shop_id = :shop_id AND order_id = :order_id"
        ),
        {"shop_id": shop_id, "order_id": order_id},
    ).scalars().all()
    for line_id in existing_line_ids:
        if line_id not in current_line_ids:
            db.execute(
                text(
                    "DELETE FROM order_line_items "
                    "WHERE shop_id = :shop_id AND id = :id"
                ),
                {"shop_id": shop_id, "id": line_id},
            )


def _delete_order(db: Session, shop_id: int, payload: dict[str, Any]) -> None:
    order_id = _gid("Order", payload.get("id"), payload.get("admin_graphql_api_id"))
    if not order_id:
        raise ValueError("Order delete webhook is missing an ID.")
    parameters = {"shop_id": shop_id, "id": order_id}
    db.execute(
        text(
            "DELETE FROM order_line_items "
            "WHERE shop_id = :shop_id AND order_id = :id"
        ),
        parameters,
    )
    db.execute(
        text("DELETE FROM orders WHERE shop_id = :shop_id AND id = :id"),
        parameters,
    )


def _mark_shop_uninstalled(db: Session, shop_id: int) -> None:
    db.execute(
        text(
            """
            UPDATE shops
            SET status = 'uninstalled',
                uninstalled_at = clock_timestamp(),
                updated_at = clock_timestamp()
            WHERE id = :shop_id
            """
        ),
        {"shop_id": shop_id},
    )


def apply_shopify_webhook(
    db: Session,
    *,
    shop_id: int,
    topic: str,
    payload: dict[str, Any],
) -> None:
    """Apply one authenticated, allowlisted Shopify webhook transactionally."""
    normalized_topic = topic.strip().lower()
    if normalized_topic not in ALLOWED_WEBHOOK_TOPICS:
        raise UnsupportedWebhookTopicError(normalized_topic)

    if normalized_topic == "app/uninstalled":
        _mark_shop_uninstalled(db, shop_id)
        return
    if normalized_topic in {"products/create", "products/update"}:
        _sync_product(db, shop_id, payload)
    elif normalized_topic == "products/delete":
        _delete_product(db, shop_id, payload)
    elif normalized_topic in {"inventory_items/create", "inventory_items/update"}:
        _sync_inventory_item(db, shop_id, payload)
    elif normalized_topic == "inventory_items/delete":
        _delete_inventory_item(db, shop_id, payload)
    elif normalized_topic in {"inventory_levels/connect", "inventory_levels/update"}:
        _sync_inventory_level(db, shop_id, payload)
    elif normalized_topic == "inventory_levels/disconnect":
        _delete_inventory_level(db, shop_id, payload)
    elif normalized_topic in {
        "locations/activate",
        "locations/create",
        "locations/deactivate",
        "locations/update",
    }:
        _sync_location(db, shop_id, payload)
    elif normalized_topic == "locations/delete":
        _delete_location(db, shop_id, payload)
    elif normalized_topic in {"orders/create", "orders/updated"}:
        _sync_order(db, shop_id, payload)
    elif normalized_topic == "orders/delete":
        _delete_order(db, shop_id, payload)

    _sync_state(db, shop_id)
