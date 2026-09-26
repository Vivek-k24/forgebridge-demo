from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

BASELINE_REVISION = "0020_catalog_coverage"
EXTRA_PRIVATE_TABLES = ("users", "auth_rate_limits")


def _connection_string() -> str:
    raw = os.environ.get("PARTGRAPH_DATABASE_URL")
    if not raw:
        raise RuntimeError("PARTGRAPH_DATABASE_URL is required")
    url = make_url(raw)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Production-copy verification requires PostgreSQL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _revision(connection: psycopg.Connection[dict[str, Any]]) -> str:
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None:
        raise AssertionError("alembic_version is empty")
    return str(row["version_num"])


def _table_exists(
    connection: psycopg.Connection[dict[str, Any]],
    table_name: str,
) -> bool:
    row = connection.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS exists",
        (f"public.{table_name}",),
    ).fetchone()
    return bool(row and row["exists"])


def _private_tables(
    connection: psycopg.Connection[dict[str, Any]],
) -> list[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'user_id'
        ORDER BY table_name
        """
    ).fetchall()
    tables = {str(row["table_name"]) for row in rows}
    for table_name in EXTRA_PRIVATE_TABLES:
        if _table_exists(connection, table_name):
            tables.add(table_name)
    return sorted(tables)


def _columns(
    connection: psycopg.Connection[dict[str, Any]],
    table_name: str,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    ).fetchall()
    columns = [str(row["column_name"]) for row in rows]
    if not columns:
        raise AssertionError(f"table {table_name!r} has no visible columns")
    return columns


def _canonical_row(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _table_fingerprint(
    connection: psycopg.Connection[dict[str, Any]],
    table_name: str,
    columns: list[str],
) -> tuple[int, str]:
    selected_columns = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    query = sql.SQL(
        "SELECT to_jsonb(snapshot_row) AS row_value "
        "FROM (SELECT {} FROM {}) AS snapshot_row"
    ).format(
        selected_columns,
        sql.Identifier("public", table_name),
    )
    canonical_rows = sorted(
        _canonical_row(row["row_value"])
        for row in connection.execute(query).fetchall()
    )
    digest = hashlib.sha256("\n".join(canonical_rows).encode("utf-8")).hexdigest()
    return len(canonical_rows), digest


def snapshot(output_path: Path) -> None:
    with psycopg.connect(_connection_string(), row_factory=dict_row) as connection:
        revision = _revision(connection)
        if revision != BASELINE_REVISION:
            raise AssertionError(
                f"production copy must start at {BASELINE_REVISION}, got {revision}"
            )

        tables: dict[str, dict[str, Any]] = {}
        for table_name in _private_tables(connection):
            columns = _columns(connection, table_name)
            row_count, digest = _table_fingerprint(connection, table_name, columns)
            tables[table_name] = {
                "columns": columns,
                "row_count": row_count,
                "sha256": digest,
            }

    payload = {
        "baseline_revision": BASELINE_REVISION,
        "tables": tables,
    }
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    total_rows = sum(int(table["row_count"]) for table in tables.values())
    print(
        "Captured production-copy owner-state fingerprint at "
        f"{BASELINE_REVISION}: {len(tables)} tables / {total_rows} rows."
    )


def verify(snapshot_path: Path, expected_revision: str) -> None:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if payload.get("baseline_revision") != BASELINE_REVISION:
        raise AssertionError("snapshot baseline revision is not the production baseline")

    expected_tables = payload.get("tables")
    if not isinstance(expected_tables, dict) or not expected_tables:
        raise AssertionError("snapshot contains no owner-state tables")

    with psycopg.connect(_connection_string(), row_factory=dict_row) as connection:
        revision = _revision(connection)
        if revision != expected_revision:
            raise AssertionError(
                f"upgraded revision: expected {expected_revision}, got {revision}"
            )

        current_private_tables = set(_private_tables(connection))
        missing_tables = sorted(set(expected_tables) - current_private_tables)
        if missing_tables:
            raise AssertionError(
                "owner-state tables disappeared during upgrade: "
                + ", ".join(missing_tables)
            )

        for table_name, expected in sorted(expected_tables.items()):
            if not isinstance(expected, dict):
                raise AssertionError(f"invalid snapshot entry for {table_name}")
            columns = expected.get("columns")
            if not isinstance(columns, list) or not all(
                isinstance(column, str) for column in columns
            ):
                raise AssertionError(f"invalid column snapshot for {table_name}")

            current_columns = set(_columns(connection, table_name))
            missing_columns = sorted(set(columns) - current_columns)
            if missing_columns:
                raise AssertionError(
                    f"{table_name} lost baseline columns: {', '.join(missing_columns)}"
                )

            row_count, digest = _table_fingerprint(
                connection,
                table_name,
                columns,
            )
            if row_count != expected.get("row_count"):
                raise AssertionError(
                    f"{table_name} row count changed: "
                    f"expected {expected.get('row_count')}, got {row_count}"
                )
            if digest != expected.get("sha256"):
                raise AssertionError(
                    f"{table_name} baseline-column digest changed during upgrade"
                )

    total_rows = sum(
        int(table["row_count"])
        for table in expected_tables.values()
        if isinstance(table, dict)
    )
    print(
        "Production-copy upgrade preserved baseline owner state and reached "
        f"{expected_revision}: {len(expected_tables)} tables / {total_rows} rows."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("snapshot", "verify"))
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--expected-revision")
    args = parser.parse_args()

    if args.mode == "snapshot":
        if args.expected_revision:
            parser.error("--expected-revision is only valid with verify")
        snapshot(args.snapshot)
        return

    if not args.expected_revision:
        parser.error("verify requires --expected-revision")
    verify(args.snapshot, args.expected_revision)


if __name__ == "__main__":
    main()
