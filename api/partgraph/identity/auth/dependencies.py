import re
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from ..config import settings
from ..database import database_connection_was_invalidated, session_factory
from ..errors import ErrorCode, PartGraphError
from .models import User
from .service import CSRF_HEADER, CSRF_VALUE, AuthenticationError, resolve_auth_session

RECOVERABLE_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
RECOVERABLE_REPAIR_IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _recoverable_repair_idempotency_key(request: Request) -> str | None:
    if request.method.upper() not in RECOVERABLE_WRITE_METHODS:
        return None
    if not request.url.path.startswith("/api/v1/repair-sessions"):
        return None
    value = request.headers.get("Idempotency-Key")
    if value is None or RECOVERABLE_REPAIR_IDEMPOTENCY_PATTERN.fullmatch(value) is None:
        return None
    return value


async def _commit_auth_transaction(
    transaction: AsyncSessionTransaction,
    request: Request,
) -> None:
    try:
        await transaction.commit()
    except DBAPIError as exc:
        idempotency_key = _recoverable_repair_idempotency_key(request)
        if idempotency_key is not None and database_connection_was_invalidated(exc):
            raise PartGraphError(
                code=ErrorCode.DATABASE_WRITE_STATE_UNCERTAIN,
                message=(
                    "PartGraph lost the database acknowledgement while confirming this repair change. "
                    "Recover the existing idempotency key before retrying."
                ),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=False,
                details={
                    "recovery_required": True,
                    "idempotency_key": idempotency_key,
                },
            ) from exc
        raise


async def get_auth_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        transaction = await session.begin()
        try:
            await session.execute(text("SET LOCAL ROLE partgraph_app"))
            yield session
        except BaseException:
            if transaction.is_active:
                await transaction.rollback()
            raise
        else:
            await _commit_auth_transaction(transaction, request)


# The transaction must finish before FastAPI sends the response. With the default
# request scope, yield-dependency cleanup happens after the response is sent, so a
# client can issue an immediate follow-up request before the previous mutation is
# committed and observe a false not-found. Function scope closes that visibility gap.
AuthSessionDep = Annotated[
    AsyncSession,
    Depends(get_auth_session, scope="function"),
]


def require_csrf(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise PartGraphError(
            code=ErrorCode.AUTH_CSRF_FAILED,
            message="CSRF validation failed.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.allowed_web_origins:
        raise PartGraphError(
            code=ErrorCode.AUTH_ORIGIN_REJECTED,
            message="Origin not allowed.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


async def current_user(request: Request, session: AuthSessionDep) -> User:
    try:
        user, _ = await resolve_auth_session(session, request.cookies.get("partgraph_session"))
    except AuthenticationError as exc:
        raise PartGraphError(
            code=exc.code,
            message=str(exc),
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    return user


CurrentUserDep = Annotated[User, Depends(current_user)]
