"""Compatibility bridge to identity-owned user-vehicle routes."""

from ..identity.user_vehicle import router as _implementation

__all__ = [name for name in dir(_implementation) if not name.startswith("__")]
globals().update({name: getattr(_implementation, name) for name in __all__})
