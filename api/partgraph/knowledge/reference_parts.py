from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .extraction import (
    MECHANICAL_CLAIM_CAPABILITY,
    ExtractedCandidate,
    ExtractionError,
    RawProviderRecord,
)

ReferenceClaimRisk = Literal["normal", "safety_critical"]
ReferenceSourceClass = Literal[
    "government",
    "oem_service",
    "licensed_oem_derived",
    "oem_parts",
    "industry_standard",
    "retailer",
    "community",
]


class ReferencePartsError(ExtractionError):
    pass


class _ReferenceVehicle(BaseModel):
    model_config = ConfigDict(extra="allow")

    vehicle_configuration_id: UUID
    market: str = Field(min_length=1)
    year: int = Field(ge=1996, le=2100)
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)


class _ReferenceReview(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["approved_for_mvp_reference"]
    reviewed_on: str = Field(min_length=1)
    reviewed_by: str = Field(min_length=1)
    note: str = Field(min_length=1)


class _ReferencePublication(BaseModel):
    part_manufacturer: str = Field(min_length=1, max_length=96)
    claim_risk: ReferenceClaimRisk
    note: str = Field(min_length=1)


class _ReferenceSource(BaseModel):
    key: str = Field(min_length=1, max_length=96)
    source_class: ReferenceSourceClass
    url: str = Field(min_length=1)


class _ReferenceComponentFile(BaseModel):
    path: str = Field(min_length=1)
    count: int = Field(ge=1)


class _ReferencePartsManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal[1]
    dataset_key: str = Field(min_length=1, max_length=160)
    vehicle: _ReferenceVehicle
    review: _ReferenceReview
    publication: _ReferencePublication
    sources: list[_ReferenceSource] = Field(min_length=1)
    exclusions: list[dict[str, object]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    component_files: dict[str, _ReferenceComponentFile] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_sources(self) -> _ReferencePartsManifest:
        keys = [source.key for source in self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError("reference parts manifest contains duplicate source keys")
        return self


class _ReferencePartRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    system: str = Field(min_length=1)
    subsystem: str = Field(min_length=1)
    name: str = Field(min_length=1)
    oem_part_number: str = Field(min_length=1, max_length=96)
    source_ref: str = Field(min_length=1, max_length=96)
    fitment_status: Literal["verified"]
    parent_assembly_part_number: str | None = None
    supersedes: list[str] = Field(default_factory=list)
    capability_note: str | None = None


class _ReferenceComponentDocument(BaseModel):
    schema_version: Literal[1]
    dataset_key: str = Field(min_length=1)
    system: str = Field(min_length=1)
    components: list[_ReferencePartRow] = Field(min_length=1)


class _ReferenceSourcePayload(BaseModel):
    dataset_key: str
    vehicle_configuration_id: UUID
    part_manufacturer: str
    claim_risk: ReferenceClaimRisk
    source_ref: str
    source_class: ReferenceSourceClass
    rows: list[_ReferencePartRow] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class PreparedReferencePartsRecord:
    dataset_key: str
    source_ref: str
    source_class: ReferenceSourceClass
    record: RawProviderRecord


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferencePartsError(
            f"reference parts file is unreadable: {path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReferencePartsError(
            f"reference parts file must be a JSON object: {path.name}"
        )
    return payload


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _bounded_key(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    prefix = value[: limit - len(digest) - 1].rstrip("._:-")
    return f"{prefix}.{digest}"


def _component_key(row: _ReferencePartRow) -> str:
    parts = (_slug(row.system), _slug(row.subsystem), _slug(row.name))
    if any(not part for part in parts):
        raise ReferencePartsError(
            "reference part row cannot produce a stable component key"
        )
    return _bounded_key(".".join(parts), limit=160)


def _normalized_claim_key(
    *,
    component_key: str,
    manufacturer: str,
    part_number: str,
) -> str:
    raw = ".".join(
        (
            "part_fitment",
            component_key,
            _slug(manufacturer),
            _slug(part_number),
        )
    )
    return _bounded_key(raw, limit=160)


def load_reference_parts_records(
    dataset_directory: Path,
    *,
    fetched_at: datetime | None = None,
) -> tuple[PreparedReferencePartsRecord, ...]:
    root = dataset_directory.resolve()
    manifest_path = root / "manifest.json"
    try:
        manifest = _ReferencePartsManifest.model_validate(_read_json(manifest_path))
    except ValidationError as exc:
        raise ReferencePartsError(
            "reference parts manifest failed validation"
        ) from exc

    source_by_key = {source.key: source for source in manifest.sources}
    rows_by_source: dict[str, list[_ReferencePartRow]] = {
        source.key: [] for source in manifest.sources
    }
    row_provenance_by_source: dict[str, list[dict[str, object]]] = {
        source.key: [] for source in manifest.sources
    }

    for declared_system, file_spec in manifest.component_files.items():
        component_path = (root / file_spec.path).resolve()
        if not component_path.is_relative_to(root):
            raise ReferencePartsError(
                "reference component file escapes its dataset directory"
            )
        try:
            document = _ReferenceComponentDocument.model_validate(
                _read_json(component_path)
            )
        except ValidationError as exc:
            raise ReferencePartsError(
                f"reference component file failed validation: {file_spec.path}"
            ) from exc
        if document.dataset_key != manifest.dataset_key:
            raise ReferencePartsError(
                f"reference component dataset key mismatch: {file_spec.path}"
            )
        if document.system != declared_system:
            raise ReferencePartsError(
                f"reference component system mismatch: {file_spec.path}"
            )
        if len(document.components) != file_spec.count:
            raise ReferencePartsError(
                f"reference component count mismatch: {file_spec.path}"
            )

        for index, row in enumerate(document.components):
            if row.system != declared_system:
                raise ReferencePartsError(
                    f"reference row system mismatch: {file_spec.path}:{index}"
                )
            if row.source_ref not in source_by_key:
                raise ReferencePartsError(
                    f"reference row uses an undeclared source: {row.source_ref}"
                )
            rows_by_source[row.source_ref].append(row)
            row_provenance_by_source[row.source_ref].append(
                {
                    "component_file": file_spec.path,
                    "component_index": index,
                    "has_parent_assembly_observation": (
                        row.parent_assembly_part_number is not None
                    ),
                    "has_supersession_observation": bool(row.supersedes),
                    "has_capability_note": row.capability_note is not None,
                }
            )

    moment = fetched_at or datetime.now(UTC)
    prepared: list[PreparedReferencePartsRecord] = []
    for source in manifest.sources:
        rows = rows_by_source[source.key]
        if not rows:
            continue
        raw_payload: dict[str, object] = {
            "dataset_key": manifest.dataset_key,
            "vehicle_configuration_id": str(
                manifest.vehicle.vehicle_configuration_id
            ),
            "part_manufacturer": manifest.publication.part_manufacturer,
            "claim_risk": manifest.publication.claim_risk,
            "source_ref": source.key,
            "source_class": source.source_class,
            "rows": [row.model_dump(mode="json") for row in rows],
        }
        record = RawProviderRecord(
            source_record_id=f"{manifest.dataset_key}:{source.key}",
            source_url=source.url,
            fetched_at=moment,
            observed_at=moment,
            raw_payload=raw_payload,
            provenance={
                "dataset_key": manifest.dataset_key,
                "dataset_schema_version": manifest.schema_version,
                "source_ref": source.key,
                "source_class": source.source_class,
                "manual_review_status": manifest.review.status,
                "manual_reviewed_on": manifest.review.reviewed_on,
                "manual_reviewed_by": manifest.review.reviewed_by,
                "manual_review_note": manifest.review.note,
                "publication_note": manifest.publication.note,
                "manifest_exclusions": manifest.exclusions,
                "manifest_notes": manifest.notes,
                "row_provenance": row_provenance_by_source[source.key],
                "deferred_fact_types": [
                    "parent_assembly_relationship",
                    "part_supersession",
                    "capability_note",
                    "manifest_exclusions",
                ],
            },
        )
        prepared.append(
            PreparedReferencePartsRecord(
                dataset_key=manifest.dataset_key,
                source_ref=source.key,
                source_class=source.source_class,
                record=record,
            )
        )
    if not prepared:
        raise ReferencePartsError(
            "reference parts dataset contains no stageable rows"
        )
    return tuple(prepared)


class ReferencePartsAdapter:
    """Convert reviewed local parts data into exact pending fitment candidates.

    The adapter deliberately materializes only exact part-fitment facts. Parent
    assembly, supersession, capability-note, and exclusion observations stay in
    immutable raw/provenance data until those domains have an explicit promotion
    contract. It performs no canonical publication.
    """

    adapter_key = "reference_parts"
    adapter_version = "v1"
    required_capability = MECHANICAL_CLAIM_CAPABILITY
    supported_provider_kinds = frozenset({"internal_data"})

    def extract(
        self,
        record: RawProviderRecord,
    ) -> tuple[ExtractedCandidate, ...]:
        try:
            payload = _ReferenceSourcePayload.model_validate(record.raw_payload)
        except ValidationError as exc:
            raise ReferencePartsError(
                "reference parts provider record failed validation"
            ) from exc

        candidates: list[ExtractedCandidate] = []
        for row in payload.rows:
            component_key = _component_key(row)
            claim_payload: dict[str, object] = {
                "component": {
                    "component_key": component_key,
                    "display_name": row.name,
                },
                "part": {
                    "manufacturer": payload.part_manufacturer,
                    "part_number": row.oem_part_number,
                    "revision": "",
                    "display_name": row.name,
                },
                "position_key": "",
                "applicability_state": "applicable",
                "qualifier_key": "",
                "qualifiers": {},
            }
            candidates.append(
                ExtractedCandidate(
                    candidate_type="mechanical_claim_candidate",
                    candidate_payload={
                        "mechanical_claim": {
                            "claim_domain": "part_fitment",
                            "claim_risk": payload.claim_risk,
                            "normalized_key": _normalized_claim_key(
                                component_key=component_key,
                                manufacturer=payload.part_manufacturer,
                                part_number=row.oem_part_number,
                            ),
                            "claim_payload": claim_payload,
                            "explicit_claim": True,
                            "exact_applicability": True,
                            "vehicle_configuration_id": str(
                                payload.vehicle_configuration_id
                            ),
                            "repair_key": None,
                        }
                    },
                    vehicle_configuration_id=payload.vehicle_configuration_id,
                )
            )
        return tuple(candidates)
