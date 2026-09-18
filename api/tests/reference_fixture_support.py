from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_PATH = (
    REPO_ROOT / "api" / "data" / "reference" / "primary_reference_bundle_v1.json"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_path(relative_path: str) -> Path:
    path = (REPO_ROOT / relative_path).resolve()
    if REPO_ROOT.resolve() not in path.parents:
        raise ValueError("Reference bundle path escapes the repository root")
    return path


def primary_bundle() -> dict[str, Any]:
    return load_json(BUNDLE_PATH)


def bundle_document(key: str) -> tuple[Path, dict[str, Any]]:
    bundle = primary_bundle()
    relative = str(bundle[key])
    path = repo_path(relative)
    return path, load_json(path)


def primary_repair_manifest() -> tuple[Path, dict[str, Any]]:
    return bundle_document("repair_manifest")


def primary_profile_manifest() -> tuple[Path, dict[str, Any]]:
    return bundle_document("profile_manifest")


def primary_parts_manifest() -> tuple[Path, dict[str, Any]]:
    return bundle_document("parts_manifest")


def primary_candidate() -> tuple[Path, dict[str, Any]]:
    return bundle_document("repair_candidate")


def primary_publication_plan() -> tuple[Path, dict[str, Any]]:
    return bundle_document("publication_plan")


def primary_vehicle_id() -> UUID:
    _, manifest = primary_repair_manifest()
    return UUID(str(manifest["vehicle_configuration_id"]))


def primary_vehicle_snapshot() -> dict[str, Any]:
    _, manifest = primary_repair_manifest()
    vehicle = dict(manifest["vehicle"])
    vehicle.setdefault("market", "US")
    return vehicle


def primary_repair(repair_key: str) -> tuple[Path, dict[str, Any]]:
    manifest_path, manifest = primary_repair_manifest()
    repair_entry = next(
        item for item in manifest["repairs"] if item["repair_key"] == repair_key
    )
    path = manifest_path.parent / str(repair_entry["path"])
    return path, load_json(path)


def primary_profile_file(file_key: str) -> tuple[Path, dict[str, Any]]:
    manifest_path, manifest = primary_profile_manifest()
    relative_name = str(manifest["files"][file_key])
    path = manifest_path.parent / relative_name
    return path, load_json(path)
