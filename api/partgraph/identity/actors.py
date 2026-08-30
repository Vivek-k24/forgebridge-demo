"""Stable authenticated-actor seam for existing application domains.

This exposes only the current owner-authenticated request dependencies. It does
not add service accounts, autonomous agents, synthetic actors, or new authority.
"""

from .auth.dependencies import AuthSessionDep, CurrentUserDep, require_csrf

__all__ = ["AuthSessionDep", "CurrentUserDep", "require_csrf"]
