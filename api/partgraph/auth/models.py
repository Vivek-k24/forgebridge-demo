"""Compatibility bridge to identity-owned authentication models."""

from ..identity.auth import models as _implementation

__all__ = [name for name in dir(_implementation) if not name.startswith("__")]
globals().update({name: getattr(_implementation, name) for name in __all__})
