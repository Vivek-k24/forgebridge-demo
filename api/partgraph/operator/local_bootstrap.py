import os
from urllib.parse import urlparse

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..identity.auth.models import User
from .models import OperatorAuditEvent
from .schemas import PreviewOperatorBootstrapStatus

_LOCAL_BOOTSTRAP_LOCK = 731_947_212
_LOCAL_WEB_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
_LOCAL_DATABASE_HOSTS = {"postgres", "localhost", "127.0.0.1"}


def local_operator_bootstrap_environment() -> bool:
    if os.getenv("PARTGRAPH_LOCAL_OPERATOR_BOOTSTRAP") != "1":
        return False
    if os.getenv("VERCEL") == "1":
        return False

    origin = os.getenv("PARTGRAPH_WEB_ORIGIN", "").strip().rstrip("/")
    if origin not in _LOCAL_WEB_ORIGINS:
        return False

    database_url = os.getenv("PARTGRAPH_DATABASE_URL", "").strip()
    if not database_url:
        return False
    database_host = urlparse(database_url).hostname
    return database_host in _LOCAL_DATABASE_HOSTS


async def local_operator_bootstrap_status(
    session: AsyncSession,
) -> PreviewOperatorBootstrapStatus:
    if not local_operator_bootstrap_environment():
        return PreviewOperatorBootstrapStatus(available=False)
    operator_id = await session.scalar(
        select(User.id).where(User.role == "operator_admin").limit(1)
    )
    return PreviewOperatorBootstrapStatus(available=operator_id is None)


async def bootstrap_local_operator(
    session: AsyncSession,
    *,
    user: User,
) -> None:
    if not local_operator_bootstrap_environment():
        raise PartGraphError(
            code=ErrorCode.REQUEST_NOT_FOUND,
            message="Local operator bootstrap is unavailable.",
            status_code=404,
        )

    await session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _LOCAL_BOOTSTRAP_LOCK})
    if user.role == "operator_admin":
        return

    operator_id = await session.scalar(
        select(User.id).where(User.role == "operator_admin").limit(1)
    )
    if operator_id is not None:
        raise PartGraphError(
            code=ErrorCode.REQUEST_CONFLICT,
            message="A local operator has already been established.",
            status_code=409,
        )

    user.role = "operator_admin"
    session.add(
        OperatorAuditEvent(
            actor_user_id=user.id,
            action="preview_operator_bootstrap",
            target_type="user",
            target_id=user.id,
            event_data={"environment": "local"},
        )
    )
    await session.flush()
