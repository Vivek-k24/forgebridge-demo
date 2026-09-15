from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "equipment"
    / "equipment_catalog_v1.json.gz"
)
_EXPECTED_SCHEMA_VERSION = 1
_FIELD_LIMITS = {
    "catalog_key": 80,
    "category": 64,
    "name": 160,
    "keywords": 500,
    "visual_key": 32,
}


class EquipmentCatalogDatasetError(RuntimeError):
    """Raised when the versioned equipment catalog dataset is malformed."""


def _require_text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise EquipmentCatalogDatasetError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise EquipmentCatalogDatasetError(f"{field} must not be empty")
    limit = _FIELD_LIMITS.get(field)
    if limit is not None and len(value) > limit:
        raise EquipmentCatalogDatasetError(
            f"{field} exceeds database limit {limit}: {len(value)}"
        )
    return value


@lru_cache(maxsize=1)
def _load_dataset() -> dict[str, Any]:
    try:
        with gzip.open(_DATASET_PATH, mode="rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise EquipmentCatalogDatasetError(
            f"could not load equipment catalog dataset: {_DATASET_PATH}"
        ) from exc

    if not isinstance(payload, dict):
        raise EquipmentCatalogDatasetError("equipment catalog dataset must be an object")
    if payload.get("schema_version") != _EXPECTED_SCHEMA_VERSION:
        raise EquipmentCatalogDatasetError(
            f"unsupported equipment catalog schema version: {payload.get('schema_version')!r}"
        )
    if not isinstance(payload.get("dataset_version"), str) or not payload[
        "dataset_version"
    ].strip():
        raise EquipmentCatalogDatasetError("dataset_version must be a non-empty string")

    categories_raw = payload.get("categories")
    if not isinstance(categories_raw, list) or not categories_raw:
        raise EquipmentCatalogDatasetError("categories must be a non-empty list")

    categories: dict[str, tuple[str, str]] = {}
    for index, entry in enumerate(categories_raw):
        if not isinstance(entry, dict):
            raise EquipmentCatalogDatasetError(f"categories[{index}] must be an object")
        key = _require_text(entry.get("key"), "category")
        label = _require_text(entry.get("label"), f"categories[{index}].label")
        visual_key = _require_text(entry.get("visual_key"), "visual_key")
        if key in categories:
            raise EquipmentCatalogDatasetError(f"duplicate category key: {key}")
        categories[key] = (label, visual_key)

    retired_raw = payload.get("retired_catalog_keys")
    if not isinstance(retired_raw, list):
        raise EquipmentCatalogDatasetError("retired_catalog_keys must be a list")
    retired: set[str] = set()
    for index, value in enumerate(retired_raw):
        key = _require_text(value, "catalog_key")
        if key in retired:
            raise EquipmentCatalogDatasetError(
                f"duplicate retired catalog key at index {index}: {key}"
            )
        retired.add(key)

    rows_raw = payload.get("rows")
    if not isinstance(rows_raw, list):
        raise EquipmentCatalogDatasetError("rows must be a list")

    rows: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for index, raw in enumerate(rows_raw):
        if not isinstance(raw, list) or len(raw) != 5:
            raise EquipmentCatalogDatasetError(
                f"rows[{index}] must contain exactly five string fields"
            )
        catalog_key = _require_text(raw[0], "catalog_key")
        category = _require_text(raw[1], "category")
        name = _require_text(raw[2], "name")
        keywords = _require_text(raw[3], "keywords", allow_empty=True)
        visual_key = _require_text(raw[4], "visual_key")
        if catalog_key in seen_keys:
            raise EquipmentCatalogDatasetError(f"duplicate catalog key: {catalog_key}")
        if catalog_key in retired:
            raise EquipmentCatalogDatasetError(
                f"retired catalog key is present in active rows: {catalog_key}"
            )
        if category not in categories:
            raise EquipmentCatalogDatasetError(
                f"catalog row {catalog_key!r} uses unknown category {category!r}"
            )
        seen_keys.add(catalog_key)
        rows.append(
            {
                "catalog_key": catalog_key,
                "category": category,
                "name": name,
                "keywords": keywords,
                "visual_key": visual_key,
            }
        )

    expected_count = payload.get("expected_item_count")
    if not isinstance(expected_count, int) or expected_count < 0:
        raise EquipmentCatalogDatasetError(
            "expected_item_count must be a non-negative integer"
        )
    if len(rows) != expected_count:
        raise EquipmentCatalogDatasetError(
            f"equipment catalog count changed: {len(rows)} != {expected_count}"
        )

    return {
        "schema_version": _EXPECTED_SCHEMA_VERSION,
        "dataset_version": payload["dataset_version"],
        "expected_item_count": expected_count,
        "categories": categories,
        "retired_catalog_keys": frozenset(retired),
        "rows": tuple(rows),
    }


def load_equipment_catalog_rows() -> list[dict[str, str]]:
    """Return mutable copies of the active versioned equipment catalog rows."""
    return [dict(row) for row in _load_dataset()["rows"]]


def load_equipment_category_meta() -> dict[str, tuple[str, str]]:
    """Return category labels and visual keys from the versioned dataset."""
    return dict(_load_dataset()["categories"])


def load_retired_catalog_keys() -> frozenset[str]:
    """Return catalog keys intentionally retired from the active dataset."""
    return _load_dataset()["retired_catalog_keys"]


def equipment_catalog_dataset_version() -> str:
    return _load_dataset()["dataset_version"]
