"""Compatibility import for the AI invocation audit model.

The audit record belongs to the provider-neutral intelligence domain. Keep this
import temporarily so code written against the Block 12A package layout does
not break during the five-PR restructuring sequence.
"""

from ..intelligence.models import AIInvocation

__all__ = ["AIInvocation"]
