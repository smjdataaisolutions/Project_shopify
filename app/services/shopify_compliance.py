import json
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


COMPLIANCE_WEBHOOK_TOPICS = frozenset(
    {"customers/data_request", "customers/redact", "shop/redact"}
)


class UnsupportedComplianceTopicError(ValueError):
    """Raised when a webhook is not a mandatory Shopify compliance topic."""


class InvalidCompliancePayloadError(ValueError):
    """Raised when a mandatory webhook omits identifiers needed for processing."""


def _order_gids(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    order_ids = set()
    for value in values:
        value_string = str(value).strip()
        if value_string.isdigit():
            order_ids.add(f"gid://shopify/Order/{value_string}")
        elif value_string.startswith("gid://shopify/Order/"):
            order_ids.add(value_string)
    return tuple(sorted(order_ids))


def apply_shopify_compliance_webhook(
    db: Session,
    *,
    shop_id: int | None,
    topic: str,
    payload: dict[str, Any],
) -> None:
    """Apply one authenticated compliance request without retaining its payload."""
    normalized_topic = topic.strip().lower()
    if normalized_topic not in COMPLIANCE_WEBHOOK_TOPICS:
        raise UnsupportedComplianceTopicError(normalized_topic)

    # A webhook for a shop already removed by shop/redact is acknowledged
    # idempotently. There is no tenant data left to export or redact.
    if shop_id is None:
        return

    parameters = {"shop_id": shop_id}
    if normalized_topic == "customers/data_request":
        data_request = payload.get("data_request")
        request_id = data_request.get("id") if isinstance(data_request, dict) else None
        request_id_string = str(request_id).strip() if request_id is not None else ""
        if not request_id_string:
            raise InvalidCompliancePayloadError("Missing data_request.id")
        # Store only the request identifier and relevant order IDs. Customer email,
        # phone, and the raw webhook payload are deliberately not retained.
        db.execute(
            text(
                """
                INSERT INTO shopify_compliance_requests (
                  shop_id, shopify_request_id, topic, order_ids
                ) VALUES (
                  :shop_id, :shopify_request_id, 'customers/data_request',
                  CAST(:order_ids AS jsonb)
                )
                ON CONFLICT (shop_id, shopify_request_id) DO UPDATE SET
                  order_ids = EXCLUDED.order_ids,
                  updated_at = clock_timestamp()
                """
            ),
            {
                **parameters,
                "shopify_request_id": request_id_string,
                "order_ids": json.dumps(
                    _order_gids(payload.get("orders_requested"))
                ),
            },
        )
        return

    if normalized_topic == "customers/redact":
        order_ids = _order_gids(payload.get("orders_to_redact"))
        if not order_ids:
            return
        order_parameters = {**parameters, "order_ids": order_ids}
        delete_lines = text(
            "DELETE FROM order_line_items "
            "WHERE shop_id = :shop_id AND order_id IN :order_ids"
        ).bindparams(bindparam("order_ids", expanding=True))
        delete_orders = text(
            "DELETE FROM orders WHERE shop_id = :shop_id AND id IN :order_ids"
        ).bindparams(bindparam("order_ids", expanding=True))
        db.execute(delete_lines, order_parameters)
        db.execute(delete_orders, order_parameters)
        return

    # shop/redact removes all analytics and the stable tenant identity.
    for table_name in (
        "shopify_compliance_requests",
        "order_line_items",
        "orders",
        "inventory",
        "product_variants",
        "products",
        "locations",
        "shopify_sync_state",
    ):
        db.execute(
            text(f"DELETE FROM {table_name} WHERE shop_id = :shop_id"),
            parameters,
        )
    db.execute(text("DELETE FROM shops WHERE id = :shop_id"), parameters)
