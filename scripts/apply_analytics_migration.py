"""Apply a reviewed analytics migration with explicit backup/database guards."""

import argparse
import hashlib
import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIR = ROOT / "migrations" / "analytics"
VERSION = "001_multi_tenant"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction", choices=("up", "down"), default="up")
    parser.add_argument("--database-url-env", default="MT_MIGRATION_DATABASE_URL")
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--backup-reference", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Required to execute. Without it, only validated metadata is printed.",
    )
    return parser.parse_args()


def main() -> None:
    args = arguments()
    raw_url = os.environ.get(args.database_url_env, "").strip()
    if not raw_url:
        raise SystemExit(f"{args.database_url_env} is required.")
    if len(args.backup_reference.strip()) < 8:
        raise SystemExit("A meaningful recoverable backup/branch reference is required.")

    path = MIGRATION_DIR / f"{VERSION}.{args.direction}.sql"
    sql = path.read_text(encoding="utf-8")
    checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    database_url = raw_url.replace("postgresql+psycopg://", "postgresql://", 1)

    with psycopg.connect(database_url) as connection:
        actual_database = connection.execute("SELECT current_database()").fetchone()[0]
        if actual_database != args.expected_database:
            raise SystemExit(
                f"Database mismatch: expected {args.expected_database!r}, "
                f"connected to {actual_database!r}."
            )
        print(f"migration={VERSION}")
        print(f"direction={args.direction}")
        print(f"database={actual_database}")
        print(f"checksum={checksum}")
        print(f"backup_reference={args.backup_reference.strip()}")
        if not args.apply:
            print("dry_run=true (no SQL executed)")
            connection.rollback()
            return

        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext('smj-analytics-schema-migration'))"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_schema_migrations (
              version TEXT PRIMARY KEY,
              checksum TEXT NOT NULL,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
            )
            """
        )
        existing = connection.execute(
            "SELECT checksum FROM analytics_schema_migrations WHERE version = %s",
            (VERSION,),
        ).fetchone()

        if args.direction == "up":
            if existing:
                if existing[0] != checksum:
                    raise SystemExit("Applied migration checksum does not match this file.")
                print("already_applied=true")
                connection.rollback()
                return
            connection.execute(sql)
            connection.execute(
                "INSERT INTO analytics_schema_migrations (version, checksum) VALUES (%s, %s)",
                (VERSION, checksum),
            )
        else:
            if not existing:
                raise SystemExit("Rollback refused: migration is not recorded as applied.")
            connection.execute(sql)
            connection.execute(
                "DELETE FROM analytics_schema_migrations WHERE version = %s",
                (VERSION,),
            )

        connection.commit()
        print("applied=true")


if __name__ == "__main__":
    main()
