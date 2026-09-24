import os
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import ErrorCode, PartGraphError
from ..identity.auth.models import User
from . import service
from .schemas import PreviewOperatorBootstrapStatus

PREVIEW_OPERATOR_BOOTSTRAP_USER_ID_ENV = "PARTGRAPH_PREVIEW_OPERATOR_BOOTSTRAP_USER_ID"


def configured_preview_operator_bootstrap_user_id() -> UUID | None:
    """Return the out-of-band authorized preview bootstrap user, failing closed."""
    raw = os.getenv(PREVIEW_OPERATOR_BOOTSTRAP_USER_ID_ENV, "").strip()
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def preview_operator_bootstrap_authorized(user: User) -> bool:
    expected_user_id = configured_preview_operator_bootstrap_user_id()
    return expected_user_id is not None and user.id == expected_user_id


async def preview_operator_bootstrap_status(
    session: AsyncSession,
    *,
    user: User,
) -> PreviewOperatorBootstrapStatus:
    if not preview_operator_bootstrap_authorized(user):
        return PreviewOperatorBootstrapStatus(available=False)
    return await service.preview_operator_bootstrap_status(session)


async def bootstrap_preview_operator(
    session: AsyncSession,
    *,
    user: User,
) -> None:
    if not preview_operator_bootstrap_authorized(user):
        raise PartGraphError(
            code=ErrorCode.REQUEST_FORBIDDEN,
            message="Preview operator bootstrap is not authorized for this account.",
            status_code=403,
        )
    await service.bootstrap_preview_operator(session, user=user)
