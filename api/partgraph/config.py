from dataclasses import dataclass
from os import getenv
from urllib.parse import urlparse


def _bool_env(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = getenv(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _web_origin() -> str:
    value = getenv("PARTGRAPH_WEB_ORIGIN", "http://localhost:5173").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
        raise ValueError("PARTGRAPH_WEB_ORIGIN must be one exact http(s) origin without a path")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    web_origin: str
    cookie_secure: bool
    session_days: int
    auth_rate_limit_attempts: int
    auth_rate_limit_minutes: int


def _load_settings() -> Settings:
    database_url = getenv(
        "PARTGRAPH_DATABASE_URL",
        "postgresql+psycopg://partgraph:partgraph@localhost:5432/partgraph",
    ).strip()
    if not database_url:
        raise ValueError("PARTGRAPH_DATABASE_URL must not be empty")

    web_origin = _web_origin()
    cookie_secure = _bool_env("PARTGRAPH_COOKIE_SECURE", False)
    if web_origin.startswith("https://") and not cookie_secure:
        raise ValueError("PARTGRAPH_COOKIE_SECURE must be enabled for an HTTPS web origin")

    return Settings(
        database_url=database_url,
        web_origin=web_origin,
        cookie_secure=cookie_secure,
        session_days=_int_env("PARTGRAPH_SESSION_DAYS", 30, minimum=1, maximum=90),
        auth_rate_limit_attempts=_int_env(
            "PARTGRAPH_AUTH_RATE_LIMIT_ATTEMPTS", 10, minimum=3, maximum=100
        ),
        auth_rate_limit_minutes=_int_env(
            "PARTGRAPH_AUTH_RATE_LIMIT_MINUTES", 15, minimum=1, maximum=1_440
        ),
    )


settings = _load_settings()
