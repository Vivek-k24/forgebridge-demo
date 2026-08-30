"""Compatibility imports for the pre-restructure repair-definition service."""

from ..knowledge.repair_service import (
    REPAIR_DEFINITION_BINDING_INVALID,
    REPAIR_DEFINITION_INTEGRITY_ERROR,
    REPAIR_DEFINITION_NOT_FOUND,
    _integrity_error,
    _manifest_for_definition,
    bound_requirement_manifest,
    verified_requirement_manifest,
)

__all__ = [
    "REPAIR_DEFINITION_NOT_FOUND",
    "REPAIR_DEFINITION_INTEGRITY_ERROR",
    "REPAIR_DEFINITION_BINDING_INVALID",
    "_integrity_error",
    "_manifest_for_definition",
    "verified_requirement_manifest",
    "bound_requirement_manifest",
]
