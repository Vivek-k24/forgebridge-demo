import asyncio
import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text, update

from partgraph.auth.models import AuthSession, User, UserPreference
from partgraph.auth.service import RateLimitError, consume_rate_limit, set_user_context
from partgraph.config import settings
from partgraph.database import session_factory
from partgraph.main import app

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}@example.com"


def test_register_session_cookie_me_preferences_and_logout() -> None:
    email = _email("register")
    with TestClient(app) as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": email.upper(), "password": PASSWORD},
            headers=CSRF,
        )
        assert registered.status_code == 200
        payload = registered.json()
        assert payload["user"]["email"] == email
        assert "token" not in payload
        cookie_header = registered.headers["set-cookie"]
        assert "HttpOnly" in cookie_header
        assert "SameSite=lax" in cookie_header

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["user"]["id"] == payload["user"]["id"]

        preferences = client.get("/api/v1/account/preferences")
        assert preferences.status_code == 200
        assert preferences.json() == {"units": "us_customary"}

        changed = client.patch(
            "/api/v1/account/preferences",
            json={"units": "metric"},
            headers=CSRF,
        )
        assert changed.status_code == 200
        assert changed.json() == {"units": "metric"}

        logout = client.post("/api/v1/auth/logout", headers=CSRF)
        assert logout.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401


def test_password_and_session_secrets_are_not_stored_in_reversible_form() -> None:
    email = _email("storage")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD},
            headers=CSRF,
        )
        assert response.status_code == 200
        raw_token = client.cookies.get("partgraph_session")
        user_id = response.json()["user"]["id"]
        assert raw_token

    async def inspect() -> None:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            assert user is not None
            assert user.password_hash != PASSWORD
            assert user.password_hash.startswith("$argon2id$")
            auth_session = (
                await session.execute(
                    select(AuthSession).where(AuthSession.user_id == user.id)
                )
            ).scalars().first()
            assert auth_session is not None
            assert auth_session.token_hash != raw_token
            assert auth_session.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()

    asyncio.run(inspect())


def test_login_is_uniform_for_wrong_password_and_unknown_account() -> None:
    email = _email("login")
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD},
            headers=CSRF,
        ).status_code == 200
        client.post("/api/v1/auth/logout", headers=CSRF)

        wrong = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong-password-value"},
            headers=CSRF,
        )
        missing = client.post(
            "/api/v1/auth/login",
            json={"email": _email("missing"), "password": "wrong-password-value"},
            headers=CSRF,
        )
        assert wrong.status_code == 401
        assert missing.status_code == 401
        assert wrong.json() == missing.json() == {"detail": "Invalid email or password."}


def test_state_changes_require_csrf_header_and_reject_foreign_origin() -> None:
    email = _email("csrf")
    with TestClient(app) as client:
        missing = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD},
        )
        foreign = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD},
            headers={**CSRF, "Origin": "https://attacker.invalid"},
        )
        assert missing.status_code == 403
        assert foreign.status_code == 403


def test_rls_blocks_cross_user_read_update_and_delete() -> None:
    email_a = _email("rls-a")
    email_b = _email("rls-b")
    with TestClient(app) as client_a, TestClient(app) as client_b:
        response_a = client_a.post(
            "/api/v1/auth/register",
            json={"email": email_a, "password": PASSWORD},
            headers=CSRF,
        )
        response_b = client_b.post(
            "/api/v1/auth/register",
            json={"email": email_b, "password": PASSWORD},
            headers=CSRF,
        )
        assert response_a.status_code == response_b.status_code == 200
        user_a = response_a.json()["user"]["id"]
        user_b = response_b.json()["user"]["id"]

    async def scenario() -> None:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                await set_user_context(session, user_a)

                own = await session.get(UserPreference, user_a)
                other = await session.get(UserPreference, user_b)
                assert own is not None
                assert other is None

                updated = await session.execute(
                    update(UserPreference)
                    .where(UserPreference.user_id == user_b)
                    .values(units="metric")
                )
                deleted = await session.execute(
                    delete(UserPreference).where(UserPreference.user_id == user_b)
                )
                assert updated.rowcount == 0
                assert deleted.rowcount == 0

    asyncio.run(scenario())


def test_database_backed_auth_rate_limit_is_shared_process_independent_state() -> None:
    email = _email("rate")

    async def scenario() -> None:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL ROLE partgraph_app"))
                for _ in range(settings.auth_rate_limit_attempts):
                    await consume_rate_limit(session, action="test", email=email)
                try:
                    await consume_rate_limit(session, action="test", email=email)
                except RateLimitError:
                    pass
                else:
                    raise AssertionError("rate limit did not reject the excess attempt")

    asyncio.run(scenario())


def test_auth_responses_include_security_headers() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
