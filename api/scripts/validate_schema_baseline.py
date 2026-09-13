from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

RESTRICT_LINE = re.compile(r"^\\(?:un)?restrict\b.*$", re.MULTILINE)
DATA_SECTION = re.compile(r"^-- Data for Name:", re.MULTILINE)
COPY_FROM_STDIN = re.compile(r"^COPY\s+.+\s+FROM\s+stdin;$", re.MULTILINE | re.IGNORECASE)


def normalized_schema(text: str) -> str:
    """Remove pg_dump invocation randomness while preserving schema semantics."""
    return RESTRICT_LINE.sub("", text).strip() + "\n"


def validate_schema_only(text: str) -> None:
    if not text.strip():
        raise ValueError("schema baseline is empty")
    if DATA_SECTION.search(text):
        raise ValueError("schema baseline contains a pg_dump data section")
    if COPY_FROM_STDIN.search(text):
        raise ValueError("schema baseline contains table data COPY statements")
    if "CREATE TABLE" not in text:
        raise ValueError("schema baseline contains no tables")
    if "CREATE SCHEMA catalog_staging" not in text:
        raise ValueError("schema baseline is missing the staging schema")
    if "CREATE POLICY" not in text:
        raise ValueError("schema baseline is missing row-level-security policies")


def write_manifest(schema_path: Path, alembic_head: str) -> Path:
    raw = schema_path.read_bytes()
    manifest = {
        "schema_version": 1,
        "alembic_head": alembic_head,
        "schema_sha256": hashlib.sha256(raw).hexdigest(),
        "schema_only": True,
        "reference_data_included": False,
        "role_bootstrap": "api/migrations/baseline/roles.sql",
        "adoption_state": "candidate_not_adopted",
    }
    manifest_path = schema_path.with_name("manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main(argv: list[str]) -> int:
    if len(argv) not in {3, 4}:
        print(
            "usage: validate_schema_baseline.py SCHEMA_SQL ALEMBIC_HEAD [RECREATED_SCHEMA_SQL]",
            file=sys.stderr,
        )
        return 2

    schema_path = Path(argv[1])
    alembic_head = argv[2]
    schema_text = schema_path.read_text(encoding="utf-8")
    validate_schema_only(schema_text)
    write_manifest(schema_path, alembic_head)

    if len(argv) == 4:
        recreated_path = Path(argv[3])
        recreated_text = recreated_path.read_text(encoding="utf-8")
        validate_schema_only(recreated_text)
        if normalized_schema(schema_text) != normalized_schema(recreated_text):
            raise ValueError("recreated baseline schema differs from migrated schema")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
