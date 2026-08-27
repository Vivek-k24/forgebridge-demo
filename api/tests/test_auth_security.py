import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text, update

from partgraph.auth.models import AuthRateLimit, AuthSession, User, UserPreference
from partgraph.auth.service import RateLimitError, consume_rate_limit, set_user_context
from partgraph.config import settings
from partgraph.database import session_factory
from partgraph.main import app

CSRF = {"X-PartGraph-CSRF": "1"}
PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "wrong-password-value"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}@example.com"


def _username(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}".casefold()


def _register(client: TestClient, prefix: str) -> tuple[dict[str, object], str, str]:
    email = _email(prefix)
    username = _username(prefix)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email.upper(), "username": username.upper(), "password": PASSWORD},
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
    return response.json(), email, username


def _error(response) -> dict[str, object]:
    payload = response.json()
    assert set(payload) == {"error"}
    error = payload["error"]
    assert isinstance(error["code"], str)
    assert isinstance(error["message"], str)
    assert isinstance(error["request_id"], str)
    assert isinstance(error["retryable"], bool)
    return error


def test_register_session_cookie_me_preferences_and_logout() -> None:
    with TestClient(app) as client:
        payload, email, username = _register(client, "register")
        assert payload["user"]["email"] == email
        assert payload["user"]["username"] == username
        assert "token" not in payload
        cookie_header = client.cookies.get("partgraph_session")
        assert cookie_header
        set_cookie = client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": PASSWORD},
            headers=CSRF,
        ).headers["set-cookie"]
        assert "HttpOnly" in set_cookie
        assert "SameSite=lax" in set_cookie

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
        signed_out = client.get("/api/v1/auth/me")
        assert signed_out.status_code == 401
        assert _error(signed_out)["code"] in {"AUTH_REQUIRED", "AUTH_SESSION_REVOKED"}


def test_login_accepts_username_or_email_case_insensitively() -> None:
    with TestClient(app) as client:
        _, email, username = _register(client, "identifier")
        assert client.post("/api/v1/auth/logout", headers=CSRF).status_code == 204

        by_username = client.post(
            "/api/v1/auth/login",
            json={"identifier": username.upper(), "password": PASSWORD},
            headers=CSRF,
        )
        assert by_username.status_code == 200
        assert by_username.json()["user"]["username"] == username
        assert client.post("/api/v1/auth/logout", headers=CSRF).status_code == 204

        by_email = client.post(
            "/api/v1/auth/login",
            json={"identifier": email.upper(), "password": PASSWORD},
            headers=CSRF,
        )
        assert by_email.status_code == 200
        assert by_email.json()["user"]["email"] == email


def test_username_is_alphanumeric_or_underscore_only_on_client_contract_and_server() -> None:
    invalid_values = [
        "has space",
        "has-hyphen",
        "has.dot",
        "has!bang",
        "has/slash",
        "has\\slash",
        "has+plus",
        "has$money",
    ]
    with TestClient(app) as client:
        for username in invalid_values:
            response = client.post(
                "/api/v1/auth/register",
                json={"email": _email("bad-user"), "username": username, "password": PASSWORD},
                headers=CSRF,
            )
            assert response.status_code == 422
            error = _error(response)
            assert error["code"] == "REQUEST_VALIDATION_FAILED"
            serialized = response.text
            assert PASSWORD not in serialized


def test_duplicate_username_or_email_returns_stable_conflict_without_race_guessing() -> None:
    with TestClient(app) as client:
        _, email, username = _register(client, "duplicate")
        duplicate_username = client.post(
            "/api/v1/auth/register",
            json={"email": _email("other"), "username": username.upper(), "password": PASSWORD},
            headers=CSRF,
        )
        duplicate_email = client.post(
            "/api/v1/auth/register",
            json={"email": email.upper(), "username": _username("other"), "password": PASSWORD},
            headers=CSRF,
        )
        assert duplicate_username.status_code == duplicate_email.status_code == 409
        assert _error(duplicate_username)["code"] == "AUTH_IDENTITY_CONFLICT"
        assert _error(duplicate_email)["code"] == "AUTH_IDENTITY_CONFLICT"


def test_password_and_session_secrets_are_not_stored_in_reversible_form() -> None:
    with TestClient(app) as client:
        response_payload, _, _ = _register(client, "storage")
        raw_token = client.cookies.get("partgraph_session")
        user_id = response_payload["user"]["id"]
        assert raw_token

    async def inspect() -> None:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            assert user is not None
            assert user.password_hash != PASSWORD
            assert user.password_hash.startswith("$argon2id$")
            auth_session = (
                await session.execute(select(AuthSession).where(AuthSession.user_id == user.id))
            ).scalars().first()
            assert auth_session is not None
            assert auth_session.token_hash != raw_token
            assert auth_session.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
            assert auth_session.expires_at.tzinfo is not None

    asyncio.run(inspect())


def test_login_is_uniform_for_wrong_password_and_unknown_account() -> None:
    with TestClient(app) as client:
        _, email, _ = _register(client, "login")
        client.post("/api/v1/auth/logout", headers=CSRF)

        wrong = client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": WRONG_PASSWORD},
            headers=CSRF,
        )
        missing = client.post(
            "/api/v1/auth/login",
            json={"identifier": _username("missing"), "password": WRONG_PASSWORD},
            headers=CSRF,
        )
        assert wrong.status_code == missing.status_code == 401
        wrong_error = _error(wrong)
        missing_error = _error(missing)
        assert wrong_error["code"] == missing_error["code"] == "AUTH_INVALID_CREDENTIALS"
        assert wrong_error["message"] == missing_error["message"]


def test_expired_session_has_explicit_code_instead_of_ambiguous_401() -> None:
    with TestClient(app) as client:
        response_payload, _, _ = _register(client, "expired")
        user_id = response_payload["user"]["id"]

        async def expire() -> None:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        update(AuthSession)
                        .where(AuthSession.user_id == user_id)
                        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
                    )

        asyncio.run(expire())
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert _error(response)["code"] == "AUTH_SESSION_EXPIRED"


def test_state_changes_require_csrf_and_reject_foreign_origin_with_codes() -> None:
    with TestClient(app) as client:
        body = {"email": _email("csrf"), "username": _username("csrf"), "password": PASSWORD}
        missing = client.post("/api/v1/auth/register", json=body)
        foreign = client.post(
            "/api/v1/auth/register",
            json=body,
            headers={**CSRF, "Origin": "https://attacker.invalid"},
        )
        assert missing.status_code == 403
        assert foreign.status_code == 403
        assert _error(missing)["code"] == "AUTH_CSRF_FAILED"
        assert _error(foreign)["code"] == "AUTH_ORIGIN_REJECTED"


def test_cors_preflight_allows_only_configured_origin_and_credentials() -> None:
    with TestClient(app) as client:
        allowed = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": settings.web_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-partgraph-csrf,x-request-id",
            },
        )
        denied = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://attacker.invalid",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == settings.web_origin
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert denied.headers.get("access-control-allow-origin") is None


def test_rls_blocks_cross_user_read_update_and_delete() -> None:
    with TestClient(app) as client_a, TestClient(app) as client_b:
        response_a, _, _ = _register(client_a, "rls_a")
        response_b, _, _ = _register(client_b, "rls_b")
        user_a = response_a["user"]["id"]
        user_b = response_b["user"]["id"]

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


def test_database_backed_rate_limit_commits_even_when_limit_raises() -> None:
    key = _email("rate")

    async def scenario() -> None:
        for _ in range(settings.auth_rate_limit_attempts):
            await consume_rate_limit(action="test", key=key)
        try:
            await consume_rate_limit(action="test", key=key)
        except RateLimitError:
            pass
        else:
            raise AssertionError("rate limit did not reject the excess attempt")

        async with session_factory() as session:
            key_hash = hashlib.sha256(key.casefold().encode()).hexdigest()
            row = await session.get(AuthRateLimit, {"action": "test", "key_hash": key_hash})
            assert row is not None
            assert row.attempts == settings.auth_rate_limit_attempts + 1

    asyncio.run(scenario())


def test_auth_payload_limit_and_error_contract_protect_server_resources() -> None:
    oversized = "x" * (17 * 1024)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=oversized,
            headers={"Content-Type": "application/json", **CSRF},
        )
    assert response.status_code == 413
    assert _error(response)["code"] == "REQUEST_PAYLOAD_TOO_LARGE"


def test_request_id_api_version_and_security_headers_are_consistent() -> None:
    request_id = "test_request_123456"
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me", headers={"X-Request-ID": request_id})
    assert response.headers["x-request-id"] == request_id
    assert response.headers["x-partgraph-api-version"] == "v1"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


def test_unknown_api_path_returns_coded_error_instead_of_silent_404() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/definitely-not-an-endpoint")
    assert response.status_code == 404
    assert _error(response)["code"] == "REQUEST_NOT_FOUND"
