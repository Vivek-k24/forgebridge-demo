from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..config import settings
from .dependencies import AuthSessionDep, CurrentUserDep, require_csrf
from .schemas import AuthResult, Credentials, PreferenceRead, PreferenceUpdate, UserRead
from .service import (
    SESSION_COOKIE,
    AuthenticationError,
    RateLimitError,
    authenticate_user,
    clear_rate_limit,
    consume_rate_limit,
    create_auth_session,
    get_preferences,
    register_user,
    revoke_auth_session,
    update_preferences,
)

router = APIRouter(prefix="/api/v1", tags=["Authentication"])
CsrfDep = Depends(require_csrf)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/auth/register", response_model=AuthResult, dependencies=[CsrfDep])
async def register(
    payload: Credentials,
    response: Response,
    session: AuthSessionDep,
) -> AuthResult:
    try:
        await consume_rate_limit(session, action="register", email=str(payload.email))
        user = await register_user(session, email=str(payload.email), password=payload.password)
        _, token = await create_auth_session(session, user.id)
        await clear_rate_limit(session, action="register", email=str(payload.email))
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(settings.auth_rate_limit_minutes * 60)},
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    _set_session_cookie(response, token)
    return AuthResult(user=UserRead.model_validate(user))


@router.post("/auth/login", response_model=AuthResult, dependencies=[CsrfDep])
async def login(
    payload: Credentials,
    response: Response,
    session: AuthSessionDep,
) -> AuthResult:
    try:
        await consume_rate_limit(session, action="login", email=str(payload.email))
        user = await authenticate_user(session, email=str(payload.email), password=payload.password)
        _, token = await create_auth_session(session, user.id)
        await clear_rate_limit(session, action="login", email=str(payload.email))
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(settings.auth_rate_limit_minutes * 60)},
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        ) from exc

    _set_session_cookie(response, token)
    return AuthResult(user=UserRead.model_validate(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[CsrfDep])
async def logout(request: Request, response: Response, session: AuthSessionDep) -> None:
    await revoke_auth_session(session, request.cookies.get(SESSION_COOKIE))
    _clear_session_cookie(response)


@router.get("/auth/me", response_model=AuthResult)
async def me(user: CurrentUserDep) -> AuthResult:
    return AuthResult(user=UserRead.model_validate(user))


@router.get("/account/preferences", response_model=PreferenceRead)
async def preferences(user: CurrentUserDep, session: AuthSessionDep) -> PreferenceRead:
    preference = await get_preferences(session, user.id)
    return PreferenceRead.model_validate(preference)


@router.patch(
    "/account/preferences",
    response_model=PreferenceRead,
    dependencies=[CsrfDep],
)
async def change_preferences(
    payload: PreferenceUpdate,
    user: CurrentUserDep,
    session: AuthSessionDep,
) -> PreferenceRead:
    preference = await update_preferences(session, user.id, units=payload.units)
    return PreferenceRead.model_validate(preference)
