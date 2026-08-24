#!/usr/bin/env python3
"""Merge append-only PartGraph SQLite catalog shards into one validated database."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from build_honda_parts_catalog import DEFAULT_SCHEMA, open_database, utc_now

TABLE_ORDER = (
    "catalog_sources",
    "vehicle_configs",
    "parts",
    "assemblies",
    "part_fitment_observations",
    "assembly_part_observations",
    "part_media_refs",
    "catalog_scrape_runs",
)


def table_columns(connection: sqlite3.Connection, schema_name: str, table: str) -> list[str]:
    rows = connection.execute(f"PRAGMA {schema_name}.table_info({table})").fetchall()
    return [str(row[1]) for row in rows]


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in TABLE_ORDER
    }


def merge_database(output: Path, inputs: list[Path], schema: Path) -> dict[str, object]:
    if not inputs:
        raise RuntimeError("At least one input catalog database is required.")

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    connection = open_database(output, schema)
    merged_inputs: list[str] = []

    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        for index, input_path in enumerate(inputs):
            if not input_path.exists():
                raise RuntimeError(f"Input catalog database is missing: {input_path}")
            alias = f"src{index}"
            connection.execute(f"ATTACH DATABASE ? AS {alias}", (str(input_path),))
            try:
                for table in TABLE_ORDER:
                    destination_columns = table_columns(connection, "main", table)
                    source_columns = table_columns(connection, alias, table)
                    if destination_columns != source_columns:
                        raise RuntimeError(
                            f"Schema mismatch for {table} in {input_path}: "
                            f"destination={destination_columns}, source={source_columns}"
                        )
                    columns = ", ".join(destination_columns)
                    connection.execute(
                        f"INSERT OR IGNORE INTO {table} ({columns}) "
                        f"SELECT {columns} FROM {alias}.{table}"
                    )

                # Keep the first non-empty observed canonical name if an OEM number was
                # inserted earlier from a shard where the parser could not infer a name.
                connection.execute(
                    f"""
                    UPDATE parts
                    SET canonical_name = (
                        SELECT source.canonical_name
                        FROM {alias}.parts AS source
                        WHERE source.oem_number = parts.oem_number
                          AND source.canonical_name IS NOT NULL
                          AND source.canonical_name <> ''
                        LIMIT 1
                    )
                    WHERE (parts.canonical_name IS NULL OR parts.canonical_name = '')
                      AND EXISTS (
                        SELECT 1
                        FROM {alias}.parts AS source
                        WHERE source.oem_number = parts.oem_number
                          AND source.canonical_name IS NOT NULL
                          AND source.canonical_name <> ''
                      )
                    """
                )
                connection.commit()
                merged_inputs.append(str(input_path))
            finally:
                connection.execute(f"DETACH DATABASE {alias}")

        connection.execute("PRAGMA foreign_keys = ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            preview = violations[:20]
            raise RuntimeError(f"Merged catalog failed foreign-key validation: {preview}")

        return {
            "output": str(output),
            "inputs": merged_inputs,
            "counts": table_counts(connection),
            "mergedAt": utc_now(),
        }
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge PartGraph SQLite catalog shards")
    parser.add_argument("--output", required=True, help="Merged SQLite database path")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Catalog schema path")
    parser.add_argument("--summary", help="Optional JSON merge-summary path")
    parser.add_argument("inputs", nargs="+", help="Input SQLite catalog databases")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = merge_database(
        Path(args.output),
        [Path(item) for item in args.inputs],
        Path(args.schema),
    )
    if args.summary:
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
