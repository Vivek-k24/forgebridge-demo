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


def _float_env(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = getenv(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _web_origin() -> str:
    value = getenv("PARTGRAPH_WEB_ORIGIN", "http://localhost:5173").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
        raise ValueError("PARTGRAPH_WEB_ORIGIN must be one exact http(s) origin without a path")
    return value


def _http_base_url(name: str, default: str) -> str:
    value = getenv(name, default).strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an http(s) URL")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    web_origin: str
    cookie_secure: bool
    session_days: int
    auth_rate_limit_attempts: int
    auth_rate_limit_minutes: int
    vin_encryption_keys: str | None
    vin_active_key_version: int
    vin_lookup_key: str | None
    vin_cache_hours: int
    nhtsa_base_url: str
    nhtsa_timeout_seconds: float


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

    vin_encryption_keys = getenv("PARTGRAPH_VIN_ENCRYPTION_KEYS")
    vin_lookup_key = getenv("PARTGRAPH_VIN_LOOKUP_KEY")

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
        vin_encryption_keys=vin_encryption_keys.strip() if vin_encryption_keys else None,
        vin_active_key_version=_int_env(
            "PARTGRAPH_VIN_ACTIVE_KEY_VERSION", 1, minimum=1, maximum=32_767
        ),
        vin_lookup_key=vin_lookup_key.strip() if vin_lookup_key else None,
        vin_cache_hours=_int_env("PARTGRAPH_VIN_CACHE_HOURS", 720, minimum=1, maximum=2_160),
        nhtsa_base_url=_http_base_url(
            "PARTGRAPH_NHTSA_BASE_URL",
            "https://vpic.nhtsa.dot.gov/api/vehicles",
        ),
        nhtsa_timeout_seconds=_float_env(
            "PARTGRAPH_NHTSA_TIMEOUT_SECONDS", 4.0, minimum=0.5, maximum=8.0
        ),
    )


settings = _load_settings()
