"""Compatibility imports for the pre-restructure catalog ORM path.

Canonical ownership moved to :mod:`partgraph.knowledge.models` in restructure
PR 2/5. Keep this module until downstream imports are cut over.
"""

from ..knowledge.models import (
    STAGING_SCHEMA,
    CatalogIngestionBatch,
    CatalogSourceRecord,
    CatalogVerifiedEvidence,
)

__all__ = [
    "STAGING_SCHEMA",
    "CatalogIngestionBatch",
    "CatalogSourceRecord",
    "CatalogVerifiedEvidence",
]
