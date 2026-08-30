"""Compatibility imports for the pre-restructure catalog staging service."""

from ..knowledge.staging import (
    CatalogStagingError,
    StageRecordInput,
    complete_ingestion_batch,
    create_ingestion_batch,
    promote_verified_record,
    reject_staging_record,
    stage_source_record,
)

__all__ = [
    "CatalogStagingError",
    "StageRecordInput",
    "create_ingestion_batch",
    "stage_source_record",
    "complete_ingestion_batch",
    "promote_verified_record",
    "reject_staging_record",
]
