from __future__ import annotations

import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

RESTRICT_LINE = re.compile(r"^\\(?:un)?restrict\b.*$", re.MULTILINE)
DATA_SECTION = re.compile(r"^-- Data for Name:", re.MULTILINE)
COPY_FROM_STDIN = re.compile(r"^COPY\s+.+\s+FROM\s+stdin;$", re.MULTILINE | re.IGNORECASE)
VARCHAR_ARRAY_CAST = re.compile(
    r"\(ARRAY\[(?P<items>(?:'(?:''|[^'])*'::character varying(?:, )?)*)\]\)::text\[\]"
)
VARCHAR_ARRAY_ITEM = re.compile(r"('(?:''|[^'])*'::character varying)")


def _normalize_varchar_array_casts(text: str) -> str:
    """Normalize one PostgreSQL deparser rewrite that is semantically identical.

    A CHECK written as ``ARRAY['x'::varchar]::text[]`` is emitted after restore
    as ``ARRAY[('x'::varchar)::text]``. Only that exact varchar-array cast form
    is normalized; different values, operators, constraints, or ACLs still
    produce a baseline mismatch.
    """

    def replace_array(match: re.Match[str]) -> str:
        items = VARCHAR_ARRAY_ITEM.sub(r"(\1)::text", match.group("items"))
        return f"ARRAY[{items}]"

    return VARCHAR_ARRAY_CAST.sub(replace_array, text)


def normalized_schema(text: str) -> str:
    """Remove known non-semantic pg_dump/deparser differences only."""
    text = RESTRICT_LINE.sub("", text)
    text = _normalize_varchar_array_casts(text)
    return text.strip() + "\n"


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


def write_schema_diff(
    schema_path: Path,
    schema_text: str,
    recreated_path: Path,
    recreated_text: str,
) -> Path:
    diff_path = schema_path.with_name("schema-diff.txt")
    diff = difflib.unified_diff(
        normalized_schema(schema_text).splitlines(keepends=True),
        normalized_schema(recreated_text).splitlines(keepends=True),
        fromfile=schema_path.name,
        tofile=recreated_path.name,
    )
    diff_path.write_text("".join(diff), encoding="utf-8")
    return diff_path


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
            diff_path = write_schema_diff(
                schema_path,
                schema_text,
                recreated_path,
                recreated_text,
            )
            raise ValueError(
                "recreated baseline schema differs from migrated schema; "
                f"inspect {diff_path}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
