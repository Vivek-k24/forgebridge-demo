"""Internal bridge to shared database infrastructure."""

from ..database import Base, get_session, session_factory

__all__ = ["Base", "get_session", "session_factory"]
