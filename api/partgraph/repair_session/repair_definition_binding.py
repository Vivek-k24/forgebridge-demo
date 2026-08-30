"""Compatibility bridge to repair-experience definition binding."""

from ..repair_experience import repair_definition_binding as _implementation

__all__ = [name for name in dir(_implementation) if not name.startswith("__")]
globals().update({name: getattr(_implementation, name) for name in __all__})
