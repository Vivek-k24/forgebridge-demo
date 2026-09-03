"""Adapters for preserving unstructured source observations before purification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ebay import CollectedObservation
from .staging import CandidateType


@dataclass(frozen=True, slots=True)
class SourceDocument:
    source_record_id: str
    source_url: str
    content: str
    content_type: str = "text/plain"
    title: str | None = None
    metadata: dict[str, Any] | None = None


def source_document_observation(
    document: SourceDocument,
    *,
    provider: str,
    dataset: str,
    provenance: dict[str, Any] | None = None,
    extracted_candidate: dict[str, Any] | None = None,
    vehicle_identity: dict[str, Any] | None = None,
    extraction_method: str = "raw_document_capture",
) -> CollectedObservation:
    """Wrap arbitrary text/HTML/XML as a lossless staging observation.

    Purifiers can later derive structured candidates from this record while
    referring back to its staging record through provenance. The source text
    is never replaced by the normalized result.
    """

    raw_payload: dict[str, Any] = {
        "content": document.content,
        "content_type": document.content_type,
        "title": document.title,
        "metadata": document.metadata or {},
    }
    candidate_payload = extracted_candidate or {
        "document_type": document.content_type,
        "title": document.title,
    }
    source_provenance: dict[str, Any] = {
        "provider": provider,
        "dataset": dataset,
    }
    if provenance:
        source_provenance.update(provenance)

    return CollectedObservation(
        source_record_id=document.source_record_id,
        source_url=document.source_url,
        candidate_type=CandidateType.SOURCE_DOCUMENT,
        raw_payload=raw_payload,
        candidate_payload=candidate_payload,
        vehicle_identity=vehicle_identity,
        provenance=source_provenance,
        extraction_method=extraction_method,
    )
