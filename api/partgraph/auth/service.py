import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from sqlalchemy import case, delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from .models import AuthRateLimit, AuthSession, User, UserPreference

SESSION_COOKIE = "partgraph_session"
CSRF_HEADER = "X-PartGraph-CSRF"
CSRF_VALUE = "1"

_password_hasher = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)
_dummy_hash = _password_hasher.hash("PartGraph-dummy-password-value")


class AuthenticationError(ValueError):
    pass


class RateLimitError(AuthenticationError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    candidate = password_hash or _dummy_hash
    try:
        valid = _password_hasher.verify(candidate, password)
    except (VerifyMismatchError, VerificationError):
        return False
    return bool(valid and password_hash is not None)


def needs_password_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _rate_key(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


async def consume_rate_limit(session: AsyncSession, *, action: str, email: str) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=settings.auth_rate_limit_minutes)
    key_hash = _rate_key(email)
    stale = AuthRateLimit.window_started_at < cutoff
    statement = (
        insert(AuthRateLimit)
        .values(action=action, key_hash=key_hash, window_started_at=now, attempts=1)
        .on_conflict_do_update(
            index_elements=["action", "key_hash"],
            set_={
                "attempts": case((stale, 1), else_=AuthRateLimit.attempts + 1),
                "window_started_at": case((stale, now), else_=AuthRateLimit.window_started_at),
            },
        )
        .returning(AuthRateLimit.attempts)
    )
    attempts = (await session.execute(statement)).scalar_one()
    if attempts > settings.auth_rate_limit_attempts:
        raise RateLimitError("Too many authentication attempts. Try again later.")


async def clear_rate_limit(session: AsyncSession, *, action: str, email: str) -> None:
    await session.execute(
        delete(AuthRateLimit).where(
            AuthRateLimit.action == action,
            AuthRateLimit.key_hash == _rate_key(email),
        )
    )


async def set_user_context(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        text("SELECT set_config('partgraph.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def register_user(session: AsyncSession, *, email: str, password: str) -> User:
    normalized = normalize_email(email)
    password_hash = await asyncio.to_thread(hash_password, password)
    created_id = (
        await session.execute(
            insert(User)
            .values(email=normalized, password_hash=password_hash, is_active=True)
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(User.id)
        )
    ).scalar_one_or_none()
    if created_id is None:
        raise AuthenticationError("An account with this email already exists.")

    user = await session.get(User, created_id)
    if user is None:
        raise RuntimeError("registered user disappeared after insert")
    await set_user_context(session, user.id)
    session.add(UserPreference(user_id=user.id, units="us_customary"))
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> User:
    normalized = normalize_email(email)
    user = (
        await session.execute(select(User).where(User.email == normalized))
    ).scalar_one_or_none()
    password_hash = user.password_hash if user is not None else None
    valid_password = await asyncio.to_thread(verify_password, password_hash, password)
    if not valid_password or user is None or not user.is_active:
        raise AuthenticationError("Invalid email or password.")

    if needs_password_rehash(user.password_hash):
        user.password_hash = await asyncio.to_thread(hash_password, password)
        await session.flush()
    return user


async def create_auth_session(session: AsyncSession, user_id: UUID) -> tuple[AuthSession, str]:
    token = new_session_token()
    now = datetime.now(UTC)
    auth_session = AuthSession(
        user_id=user_id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(days=settings.session_days),
        last_seen_at=now,
    )
    session.add(auth_session)
    await session.flush()
    return auth_session, token


async def resolve_auth_session(session: AsyncSession, token: str | None) -> tuple[User, AuthSession]:
    if not token:
        raise AuthenticationError("Authentication required.")
    now = datetime.now(UTC)
    auth_session = (
        await session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
    ).scalar_one_or_none()
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
        raise AuthenticationError("Authentication required.")

    user = await session.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Authentication required.")

    if auth_session.last_seen_at < now - timedelta(minutes=5):
        auth_session.last_seen_at = now
        await session.flush()
    await set_user_context(session, user.id)
    return user, auth_session


async def revoke_auth_session(session: AsyncSession, token: str | None) -> None:
    if not token:
        return
    auth_session = (
        await session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
    ).scalar_one_or_none()
    if auth_session is not None and auth_session.revoked_at is None:
        auth_session.revoked_at = datetime.now(UTC)
        await session.flush()


async def get_preferences(session: AsyncSession, user_id: UUID) -> UserPreference:
    preference = await session.get(UserPreference, user_id)
    if preference is None:
        preference = UserPreference(user_id=user_id, units="us_customary")
        session.add(preference)
        await session.flush()
    return preference


async def update_preferences(
    session: AsyncSession, user_id: UUID, *, units: str
) -> UserPreference:
    preference = await get_preferences(session, user_id)
    preference.units = units
    preference.updated_at = datetime.now(UTC)
    await session.flush()
    return preference
