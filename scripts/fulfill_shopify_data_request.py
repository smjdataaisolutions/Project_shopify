"""Export or complete one authenticated Shopify customer data request.

This operator-only tool never prints exported records or database credentials.
Use ``complete`` only after the export has been delivered securely to the store
owner who initiated the request.
"""

import argparse
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import psycopg
from psycopg.rows import dict_row


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("list", "export", "complete"))
    parser.add_argument("--shop-domain")
    parser.add_argument("--request-id")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--database-url-env", default="SHOPIFY_COMPLIANCE_DATABASE_URL"
    )
    return parser.parse_args()


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported export value: {type(value).__name__}")


def main() -> None:
    args = arguments()
    if args.action in {"export", "complete"} and (
        not args.shop_domain or not args.request_id
    ):
        raise SystemExit("--shop-domain and --request-id are required.")
    if args.action == "export" and args.output is None:
        raise SystemExit("--output is required for export.")
    if args.action != "export" and args.output is not None:
        raise SystemExit("--output is valid only for export.")

    raw_url = os.environ.get(args.database_url_env, "").strip()
    if not raw_url:
        raise SystemExit(f"{args.database_url_env} is required.")
    database_url = raw_url.replace("postgresql+psycopg://", "postgresql://", 1)

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        if args.action == "list":
            shop_filter = args.shop_domain.strip().lower() if args.shop_domain else None
            list_sql = """
                SELECT shop.shop_domain, request.shopify_request_id,
                       request.status, request.received_at, request.due_at,
                       jsonb_array_length(request.order_ids) AS order_count
                FROM shopify_compliance_requests request
                JOIN shops shop ON shop.id = request.shop_id
                WHERE request.status <> 'completed'
            """
            if shop_filter:
                rows = connection.execute(
                    list_sql
                    + " AND shop.shop_domain = %s "
                    + "ORDER BY request.due_at, shop.shop_domain",
                    (shop_filter,),
                ).fetchall()
            else:
                rows = connection.execute(
                    list_sql + " ORDER BY request.due_at, shop.shop_domain"
                ).fetchall()
            for row in rows:
                print(
                    f"shop={row['shop_domain']} "
                    f"request={row['shopify_request_id']} "
                    f"status={row['status']} due={row['due_at'].isoformat()} "
                    f"orders={row['order_count']}"
                )
            print(f"open_requests={len(rows)}")
            connection.rollback()
            return

        request = connection.execute(
            """
            SELECT request.id, request.shop_id, request.shopify_request_id,
                   request.order_ids, request.status, request.received_at,
                   request.due_at
            FROM shopify_compliance_requests request
            JOIN shops shop ON shop.id = request.shop_id
            WHERE shop.shop_domain = %s AND request.shopify_request_id = %s
            FOR UPDATE
            """,
            (args.shop_domain.strip().lower(), args.request_id.strip()),
        ).fetchone()
        if request is None:
            raise SystemExit("Compliance request not found for that shop.")

        if args.action == "complete":
            connection.execute(
                """
                UPDATE shopify_compliance_requests
                SET status = 'completed', completed_at = clock_timestamp(),
                    updated_at = clock_timestamp()
                WHERE id = %s
                """,
                (request["id"],),
            )
            connection.commit()
            print("status=completed")
            return

        order_ids = request["order_ids"]
        orders = []
        line_items = []
        if order_ids:
            orders = connection.execute(
                "SELECT * FROM orders WHERE shop_id = %s AND id = ANY(%s) ORDER BY id",
                (request["shop_id"], order_ids),
            ).fetchall()
            line_items = connection.execute(
                """
                SELECT * FROM order_line_items
                WHERE shop_id = %s AND order_id = ANY(%s)
                ORDER BY order_id, id
                """,
                (request["shop_id"], order_ids),
            ).fetchall()

        document = {
            "shop_domain": args.shop_domain.strip().lower(),
            "shopify_request_id": request["shopify_request_id"],
            "received_at": request["received_at"],
            "due_at": request["due_at"],
            "orders": orders,
            "order_line_items": line_items,
        }
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, delete=False
        ) as temporary:
            json.dump(document, temporary, default=json_default, indent=2)
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        temporary_path.replace(output)

        connection.execute(
            """
            UPDATE shopify_compliance_requests
            SET status = 'exported', updated_at = clock_timestamp()
            WHERE id = %s AND status <> 'completed'
            """,
            (request["id"],),
        )
        connection.commit()
        print(f"status=exported records={len(orders)} line_items={len(line_items)}")
        print(f"output={output}")


if __name__ == "__main__":
    main()
