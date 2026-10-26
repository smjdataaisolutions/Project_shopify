"""Print non-secret Shopify session metadata for staging diagnostics."""

import os
import sys

import psycopg


def main():
    database_url = os.environ["SHOPIFY_SESSION_DATABASE_URL"]
    shop = os.environ["SHOPIFY_STORE"].strip().lower()
    if not shop.endswith(".myshopify.com"):
        raise RuntimeError("SHOPIFY_STORE must be a canonical .myshopify.com domain.")

    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            """
            SELECT id, shop, scope, expires, "isOnline", length("accessToken")
            FROM "Session"
            WHERE shop = %s
            ORDER BY expires DESC NULLS FIRST
            """,
            (shop,),
        ).fetchall()

    print(f"session_count={len(rows)}")
    for session_id, session_shop, scopes, expires, online, token_length in rows:
        print(
            f"session_id={session_id} shop={session_shop} scopes={scopes} "
            f"expires={expires} online={online} token_present={bool(token_length)}"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"session_metadata_check_failed={type(error).__name__}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
