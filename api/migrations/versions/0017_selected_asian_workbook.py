"""Import the reviewed selected-Asian-brands workbook as unverified identity candidates.

The workbook is intentionally a breadth-limited collection proof.  It is useful
for vehicle selection, but it does not retain authoritative per-row source
citations.  Rows therefore remain unverified and are not promoted to verified
evidence or mechanical claims.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0017_selected_asian_workbook"
down_revision: str | None = "0016_vehicle_identity_bootstrap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKBOOK_NAME = "Selected_Asian_Brands_1996_2000.xlsx"
WORKBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / WORKBOOK_NAME
SOURCE_COMMIT = "ab954125d89f8ae4cfc42d35af177ec1fe3938a8"
SOURCE_URL = (
    "https://github.com/Vivek-k24/forgebridge-demo/blob/"
    f"{SOURCE_COMMIT}/docs/{WORKBOOK_NAME}"
)
EXPECTED_HEADERS = (
    "Year",
    "Make",
    "Model",
    "Trim",
    "Engine Specs",
    "Transmission Specs",
)
EXPECTED_ROW_COUNT = 363
IMPORT_NAMESPACE = UUID("b501a93e-fc83-5f3f-8f62-0c53ac1783c4")
BATCH_ID = uuid5(IMPORT_NAMESPACE, f"batch:{SOURCE_COMMIT}:{WORKBOOK_NAME}")
XML_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
OPTIONAL_FIELDS = ("generation", "trim", "body_style", "engine", "transmission", "drivetrain")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _compact(value: str | None) -> str:
    if not value:
        return ""
    return "".join(character for character in value.casefold() if character.isalnum())


def _comparison_key(field: str, value: str | None) -> str:
    if not value:
        return ""
    if field in {"engine", "transmission"}:
        keys = {_compact(token) for token in value.split() if _compact(token)}
        return "|".join(sorted(keys))
    return _compact(value)


def _sha(parts: Sequence[str]) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _cell_value(cell: ET.Element) -> str | None:
    if cell.get("t") == "inlineStr":
        text = "".join(node.text or "" for node in cell.findall(".//x:t", XML_NS))
        return _clean(text)
    value = cell.find("x:v", XML_NS)
    return _clean(value.text if value is not None else None)


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if letters is None:
        raise RuntimeError(f"Invalid XLSX cell reference: {reference}")
    index = 0
    for character in letters.group(0):
        index = index * 26 + (ord(character) - ord("A") + 1)
    return index - 1


def _read_rows() -> list[tuple[int, tuple[str, ...]]]:
    if not WORKBOOK_PATH.exists():
        raise RuntimeError(f"Curated vehicle workbook is missing: {WORKBOOK_PATH}")

    with zipfile.ZipFile(WORKBOOK_PATH) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    parsed: list[tuple[int, tuple[str, ...]]] = []
    for row in root.findall(".//x:sheetData/x:row", XML_NS):
        excel_row = int(row.get("r", "0"))
        values: list[str | None] = [None] * len(EXPECTED_HEADERS)
        for cell in row.findall("x:c", XML_NS):
            reference = cell.get("r", "")
            index = _column_index(reference)
            if index < len(values):
                values[index] = _cell_value(cell)
        parsed.append((excel_row, tuple(value or "" for value in values)))

    if not parsed or parsed[0][1] != EXPECTED_HEADERS:
        raise RuntimeError(
            f"Unexpected workbook headers: {parsed[0][1] if parsed else None!r}"
        )

    data_rows = parsed[1:]
    if len(data_rows) != EXPECTED_ROW_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_ROW_COUNT} vehicle rows, found {len(data_rows)}"
        )
    if len({row for _, row in data_rows}) != EXPECTED_ROW_COUNT:
        raise RuntimeError("Workbook contains duplicate six-column vehicle rows")
    return data_rows


def _normalized(raw: tuple[str, ...]) -> dict[str, int | str | None]:
    year_raw, make_raw, model_raw, trim_raw, engine_raw, transmission_raw = raw
    year = int(year_raw)
    if year < 1996 or year > 2000:
        raise RuntimeError(f"Workbook year is outside the approved import range: {year}")

    make = _clean(make_raw)
    model = _clean(model_raw)
    if not make or not model:
        raise RuntimeError(f"Workbook row is missing make/model: {raw!r}")

    return {
        "year": year,
        "market": "US",
        "make": make,
        "model": model.upper(),
        "generation": None,
        "trim": (_clean(trim_raw) or "").upper() or None,
        "body_style": None,
        "engine": _clean(engine_raw),
        "transmission": _clean(transmission_raw),
        "drivetrain": None,
    }


def _base_hash(values: dict[str, int | str | None]) -> str:
    return _sha(
        (
            str(values["year"]),
            str(values["market"]),
            str(values["make"]),
            _comparison_key("model", str(values["model"])),
        )
    )


def _identity_hash(values: dict[str, int | str | None]) -> str:
    parts = [
        str(values["year"]),
        str(values["market"]),
        str(values["make"]),
        _comparison_key("model", str(values["model"])),
    ]
    parts.extend(
        _comparison_key(field, values[field] if isinstance(values[field], str) else None)
        for field in OPTIONAL_FIELDS
    )
    return _sha(tuple(parts))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _row_ids(excel_row: int, identity_hash: str) -> tuple[UUID, UUID]:
    source_record_id = uuid5(
        IMPORT_NAMESPACE,
        f"source:{SOURCE_COMMIT}:{WORKBOOK_NAME}:{excel_row}:{identity_hash}",
    )
    vehicle_id = uuid5(IMPORT_NAMESPACE, f"vehicle:{identity_hash}")
    return source_record_id, vehicle_id


def upgrade() -> None:
    bind = op.get_bind()
    workbook_sha256 = hashlib.sha256(WORKBOOK_PATH.read_bytes()).hexdigest()
    rows = _read_rows()

    bind.execute(
        sa.text(
            """
            INSERT INTO catalog_staging.ingestion_batches (
                id, source_name, source_type, collector_version, status,
                started_at, completed_at, created_at
            ) VALUES (
                :id, :source_name, 'curated_workbook', 'workbook-import-1', 'completed',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": BATCH_ID,
            "source_name": f"github:{SOURCE_COMMIT}:{WORKBOOK_NAME}",
        },
    )

    for excel_row, raw in rows:
        values = _normalized(raw)
        identity_hash = _identity_hash(values)
        base_identity_hash = _base_hash(values)
        source_record_uuid, vehicle_uuid = _row_ids(excel_row, identity_hash)
        row_payload = dict(zip(EXPECTED_HEADERS, raw, strict=True))
        provenance = {
            "artifact": WORKBOOK_NAME,
            "repository_commit": SOURCE_COMMIT,
            "excel_row": excel_row,
            "workbook_sha256": workbook_sha256,
            "review_boundary": (
                "User manually spot-checked model/trim breadth. Authoritative per-row source "
                "citations were not retained, so this candidate is intentionally unverified."
            ),
        }
        dedupe_key = hashlib.sha256(
            f"{SOURCE_COMMIT}:{WORKBOOK_NAME}:{excel_row}:{_json(row_payload)}".encode()
        ).hexdigest()

        bind.execute(
            sa.text(
                """
                INSERT INTO catalog_staging.source_records (
                    id, batch_id, source_record_id, source_url, fetched_at, observed_at,
                    candidate_type, raw_sha256, raw_payload, candidate_payload,
                    vehicle_identity, provenance, extraction_method, confidence,
                    review_status, reviewed_at, reviewed_by, dedupe_key, created_at
                ) VALUES (
                    :id, :batch_id, :source_record_id, :source_url,
                    CURRENT_TIMESTAMP, NULL, 'vehicle_identity', :raw_sha256,
                    CAST(:raw_payload AS JSONB), CAST(:candidate_payload AS JSONB),
                    CAST(:vehicle_identity AS JSONB), CAST(:provenance AS JSONB),
                    'curated_workbook_import', NULL, 'pending', NULL, NULL,
                    :dedupe_key, CURRENT_TIMESTAMP
                )
                ON CONFLICT (dedupe_key) DO NOTHING
                """
            ),
            {
                "id": source_record_uuid,
                "batch_id": BATCH_ID,
                "source_record_id": f"{WORKBOOK_NAME}:row:{excel_row}",
                "source_url": SOURCE_URL,
                "raw_sha256": hashlib.sha256(_json(row_payload).encode()).hexdigest(),
                "raw_payload": _json(row_payload),
                "candidate_payload": _json(values),
                "vehicle_identity": _json(values),
                "provenance": _json(provenance),
                "dedupe_key": dedupe_key,
            },
        )

        bind.execute(
            sa.text(
                """
                INSERT INTO vehicle_configurations (
                    id, identity_hash, base_identity_hash, canonicalization_version,
                    year, market, make, model, generation, trim, body_style, engine,
                    transmission, drivetrain, identity_source, verification_status,
                    created_at, updated_at
                ) VALUES (
                    :id, :identity_hash, :base_identity_hash, 2,
                    :year, :market, :make, :model, :generation, :trim, :body_style,
                    :engine, :transmission, :drivetrain, 'workbook', 'unverified',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (identity_hash) DO NOTHING
                """
            ),
            {
                "id": vehicle_uuid,
                "identity_hash": identity_hash,
                "base_identity_hash": base_identity_hash,
                **values,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = _read_rows()
    vehicle_ids = []
    for excel_row, raw in rows:
        values = _normalized(raw)
        identity_hash = _identity_hash(values)
        _, vehicle_uuid = _row_ids(excel_row, identity_hash)
        vehicle_ids.append(vehicle_uuid)

    bind.execute(
        sa.text("DELETE FROM catalog_staging.source_records WHERE batch_id = :batch_id"),
        {"batch_id": BATCH_ID},
    )
    bind.execute(
        sa.text("DELETE FROM catalog_staging.ingestion_batches WHERE id = :batch_id"),
        {"batch_id": BATCH_ID},
    )

    for vehicle_id in vehicle_ids:
        bind.execute(
            sa.text(
                """
                DELETE FROM vehicle_configurations
                WHERE id = :vehicle_id
                  AND identity_source = 'workbook'
                  AND verification_status = 'unverified'
                  AND NOT EXISTS (
                      SELECT 1 FROM user_vehicles
                      WHERE canonical_configuration_id = :vehicle_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM repair_definitions
                      WHERE vehicle_configuration_id = :vehicle_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM mechanical_claims
                      WHERE vehicle_configuration_id = :vehicle_id
                  )
                """
            ),
            {"vehicle_id": vehicle_id},
        )
