from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

from validate_schema_baseline import validate_schema_only

BASELINE_DIR = Path(__file__).resolve().parents[1] / "migrations" / "baseline"
ARCHIVE_PATH = BASELINE_DIR / "schema.sql.gz.b64"
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
EXPECTED_ADOPTION_STATE = "adopted"
EXPECTED_HEAD = "0045_provenance_conflicts"


def load_adopted_schema() -> bytes:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("adoption_state") != EXPECTED_ADOPTION_STATE:
        raise ValueError("baseline manifest is not marked adopted")
    if manifest.get("alembic_head") != EXPECTED_HEAD:
        raise ValueError(
            "baseline Alembic head mismatch: "
            f"expected {EXPECTED_HEAD}, got {manifest.get('alembic_head')}"
        )
    if manifest.get("schema_only") is not True:
        raise ValueError("adopted baseline must be schema-only")
    if manifest.get("reference_data_included") is not False:
        raise ValueError("reference data must remain outside the schema baseline")

    encoded = ARCHIVE_PATH.read_text(encoding="ascii")
    raw = gzip.decompress(base64.b64decode(encoded))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest.get("schema_sha256"):
        raise ValueError(
            "adopted baseline checksum mismatch: "
            f"expected {manifest.get('schema_sha256')}, got {digest}"
        )

    validate_schema_only(raw.decode("utf-8"))
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify and optionally decode the adopted PartGraph schema baseline."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the verified schema SQL to this path.",
    )
    args = parser.parse_args()

    raw = load_adopted_schema()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)

    print(
        "verified adopted schema baseline "
        f"({len(raw)} bytes, head {EXPECTED_HEAD})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
