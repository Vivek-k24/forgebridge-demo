import hashlib
import json
import unittest
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient

from partgraph.config import settings
from partgraph.identity.auth.service import CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE
from partgraph.main import app

PASSWORD = "Phase9-Secure-Password!"
WRONG_PASSWORD = "Phase9-Wrong-Password!"


class FinalMvpAuthenticationSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            app,
            base_url=settings.web_origin,
            raise_server_exceptions=False,
        )

    def tearDown(self) -> None:
        self.client.close()

    def _identity(self, prefix: str) -> tuple[str, str]:
        suffix = uuid4().hex[:12]
        username = f"{prefix}_{suffix}"
        return username, f"{username}@example.com"

    def _csrf_headers(self, *, origin: str | None = None) -> dict[str, str]:
        headers = {CSRF_HEADER: CSRF_VALUE}
        if origin is not None:
            headers["Origin"] = origin
        return headers

    def _register(self, prefix: str = "phase9auth") -> tuple[str, str, object]:
        username, email = self._identity(prefix)
        response = self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": PASSWORD},
            headers=self._csrf_headers(origin=settings.web_origin),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return username, email, response

    def _stored_auth_secrets(self, email: str) -> tuple[str, str]:
        database_url = settings.database_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1,
        )
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT users.password_hash, auth_sessions.token_hash
                    FROM users
                    JOIN auth_sessions ON auth_sessions.user_id = users.id
                    WHERE users.email = %s
                    ORDER BY auth_sessions.created_at DESC
                    LIMIT 1
                    """,
                    (email,),
                )
                row = cursor.fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        return str(row[0]), str(row[1])

    def test_protected_identity_endpoint_requires_authentication(self) -> None:
        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "AUTH_REQUIRED")
        self.assertEqual(response.json()["error"]["message"], "Authentication required.")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_auth_mutations_require_csrf_and_reject_untrusted_origin(self) -> None:
        username, email = self._identity("phase9csrf")
        payload = {"email": email, "username": username, "password": PASSWORD}

        missing_csrf = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["error"]["code"], "AUTH_CSRF_FAILED")

        hostile_origin = self.client.post(
            "/api/v1/auth/register",
            json=payload,
            headers=self._csrf_headers(origin="https://attacker.example"),
        )
        self.assertEqual(hostile_origin.status_code, 403)
        self.assertEqual(hostile_origin.json()["error"]["code"], "AUTH_ORIGIN_REJECTED")

    def test_registration_hardens_cookie_and_stores_only_password_and_token_hashes(self) -> None:
        username, email, response = self._register("phase9cookie")
        payload_text = json.dumps(response.json(), sort_keys=True)

        self.assertEqual(response.json()["user"]["username"], username)
        self.assertNotIn(PASSWORD, payload_text)
        self.assertNotIn("password_hash", payload_text)
        self.assertNotIn("token", payload_text)

        set_cookie = response.headers["set-cookie"]
        self.assertIn(f"{SESSION_COOKIE}=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        self.assertIn("Path=/", set_cookie)
        self.assertIn("Secure", set_cookie)
        self.assertEqual(
            response.headers["strict-transport-security"],
            "max-age=31536000; includeSubDomains",
        )

        token = self.client.cookies.get(SESSION_COOKIE)
        self.assertIsNotNone(token)
        assert token is not None
        password_hash, token_hash = self._stored_auth_secrets(email)

        self.assertNotEqual(password_hash, PASSWORD)
        self.assertTrue(password_hash.startswith("$argon2"))
        self.assertNotEqual(token_hash, token)
        self.assertEqual(token_hash, hashlib.sha256(token.encode("utf-8")).hexdigest())

    def test_logout_requires_csrf_then_revokes_the_active_session(self) -> None:
        username, _, _ = self._register("phase9logout")

        authenticated = self.client.get("/api/v1/auth/me")
        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(authenticated.json()["user"]["username"], username)

        rejected_logout = self.client.post("/api/v1/auth/logout")
        self.assertEqual(rejected_logout.status_code, 403)
        self.assertEqual(rejected_logout.json()["error"]["code"], "AUTH_CSRF_FAILED")
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)

        logout = self.client.post(
            "/api/v1/auth/logout",
            headers=self._csrf_headers(origin=settings.web_origin),
        )
        self.assertEqual(logout.status_code, 204)
        self.assertIn(f"{SESSION_COOKIE}=", logout.headers["set-cookie"])

        after_logout = self.client.get("/api/v1/auth/me")
        self.assertEqual(after_logout.status_code, 401)
        self.assertEqual(after_logout.json()["error"]["code"], "AUTH_REQUIRED")

    def test_invalid_login_does_not_reveal_whether_identity_exists(self) -> None:
        username, _, _ = self._register("phase9enum")
        headers = self._csrf_headers(origin=settings.web_origin)

        known_identity = self.client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": WRONG_PASSWORD},
            headers=headers,
        )
        unknown_identity = self.client.post(
            "/api/v1/auth/login",
            json={"identifier": f"missing_{uuid4().hex[:12]}", "password": WRONG_PASSWORD},
            headers=headers,
        )

        self.assertEqual(known_identity.status_code, 401)
        self.assertEqual(unknown_identity.status_code, 401)
        for response in (known_identity, unknown_identity):
            error = response.json()["error"]
            self.assertEqual(error["code"], "AUTH_INVALID_CREDENTIALS")
            self.assertEqual(error["message"], "Invalid username/email or password.")

    def test_failed_login_rate_limit_persists_across_request_rollbacks(self) -> None:
        identifier = f"rate_{uuid4().hex[:12]}"
        headers = self._csrf_headers(origin=settings.web_origin)
        payload = {"identifier": identifier, "password": WRONG_PASSWORD}

        for attempt in range(settings.auth_rate_limit_attempts):
            response = self.client.post("/api/v1/auth/login", json=payload, headers=headers)
            with self.subTest(attempt=attempt + 1):
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json()["error"]["code"], "AUTH_INVALID_CREDENTIALS")

        limited = self.client.post("/api/v1/auth/login", json=payload, headers=headers)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["error"]["code"], "AUTH_RATE_LIMITED")
        self.assertTrue(limited.json()["error"]["retryable"])
        self.assertEqual(
            limited.headers["retry-after"],
            str(settings.auth_rate_limit_minutes * 60),
        )


if __name__ == "__main__":
    unittest.main()
