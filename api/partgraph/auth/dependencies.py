from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import session_factory
from ..errors import ErrorCode, PartGraphError
from .models import User
from .service import CSRF_HEADER, CSRF_VALUE, AuthenticationError, resolve_auth_session


async def get_auth_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL ROLE partgraph_app"))
            yield session


AuthSessionDep = Annotated[AsyncSession, Depends(get_auth_session)]


def require_csrf(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise PartGraphError(
            code=ErrorCode.AUTH_CSRF_FAILED,
            message="CSRF validation failed.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") != settings.web_origin.rstrip("/"):
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
