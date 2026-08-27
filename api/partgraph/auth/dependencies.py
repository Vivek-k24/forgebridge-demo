from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import session_factory
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") != settings.web_origin.rstrip("/"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed.")


async def current_user(request: Request, session: AuthSessionDep) -> User:
    try:
        user, _ = await resolve_auth_session(session, request.cookies.get("partgraph_session"))
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        ) from exc
    return user


CurrentUserDep = Annotated[User, Depends(current_user)]
