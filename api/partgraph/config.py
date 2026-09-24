import os
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_DATABASE_URL = "postgresql+psycopg://partgraph:partgraph@localhost:5432/partgraph"
DEFAULT_WEB_ORIGIN = "http://localhost:5173"
DEFAULT_NHTSA_TIMEOUT_SECONDS = 4.0
DEFAULT_REQUEST_DEADLINE_SECONDS = 8.0
MAX_REQUEST_DEADLINE_SECONDS = 9.0
MAX_PROVIDER_DEADLINE_RESERVE_SECONDS = 1.0
DEFAULT_PROVIDER_INGESTION_MODE = "operator_sync"
SUPPORTED_PROVIDER_INGESTION_MODES = frozenset({DEFAULT_PROVIDER_INGESTION_MODE})


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float_env(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _provider_ingestion_mode() -> str:
    mode = os.getenv(
        "PARTGRAPH_PROVIDER_INGESTION_MODE",
        DEFAULT_PROVIDER_INGESTION_MODE,
    ).strip().casefold()
    if mode not in SUPPORTED_PROVIDER_INGESTION_MODES:
        raise ValueError(
            "PARTGRAPH_PROVIDER_INGESTION_MODE only supports 'operator_sync' for the MVP; "
            "scheduled, continuous, bulk, or worker ingestion requires the documented "
            "durable queue/backpressure design before it can be enabled"
        )
    return mode


def _validate_provider_timeout_hierarchy(
    *,
    provider_timeout_seconds: float,
    request_deadline_seconds: float,
) -> None:
    # Normal API budgets retain a full second after the upstream provider has
    # timed out. Very small explicitly configured deadlines retain half of the
    # business deadline so the provider can still use the supported 0.5 s floor.
    reserve_seconds = min(
        MAX_PROVIDER_DEADLINE_RESERVE_SECONDS,
        request_deadline_seconds / 2,
    )
    maximum_provider_timeout = request_deadline_seconds - reserve_seconds
    if provider_timeout_seconds > maximum_provider_timeout:
        raise ValueError(
            "PARTGRAPH_NHTSA_TIMEOUT_SECONDS must leave provider/API deadline reserve: "
            f"provider timeout must be <= {maximum_provider_timeout:g}s when "
            f"PARTGRAPH_REQUEST_DEADLINE_SECONDS is {request_deadline_seconds:g}s"
        )


def _database_url() -> str:
    partgraph_value = os.getenv("PARTGRAPH_DATABASE_URL")
    value = partgraph_value if partgraph_value is not None else os.getenv("DATABASE_URL")
    database_url = (value if value is not None else DEFAULT_DATABASE_URL).strip()
    if not database_url:
        raise ValueError("PARTGRAPH_DATABASE_URL/DATABASE_URL must not be empty")

    if database_url.startswith("postgres://"):
        return f"postgresql+psycopg://{database_url[len('postgres://') :]}"
    if database_url.startswith("postgresql://"):
        return f"postgresql+psycopg://{database_url[len('postgresql://') :]}"
    return database_url


def _database_pooling(*, running_on_vercel: bool) -> bool:
    enabled = _bool_env("PARTGRAPH_DATABASE_POOLING", not running_on_vercel)
    if running_on_vercel and enabled:
        raise ValueError(
            "PARTGRAPH_DATABASE_POOLING must be disabled on Vercel; "
            "serverless instances must not retain per-instance SQLAlchemy pools"
        )
    return enabled


def _validate_origin(value: str, *, source: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
        raise ValueError(f"{source} must be one exact http(s) origin without a path")
    return normalized


def _web_origin() -> str:
    explicit_origin = os.getenv("PARTGRAPH_WEB_ORIGIN")
    if explicit_origin is not None:
        value = explicit_origin
    else:
        vercel_production_host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL")
        value = (
            f"https://{vercel_production_host.strip().rstrip('/')}"
            if vercel_production_host
            else DEFAULT_WEB_ORIGIN
        )
    return _validate_origin(value, source="PARTGRAPH_WEB_ORIGIN")


def _allowed_web_origins(primary_origin: str) -> frozenset[str]:
    origins = {primary_origin.rstrip("/")}
    if os.getenv("VERCEL") != "1" or os.getenv("VERCEL_ENV") != "preview":
        return frozenset(origins)

    for variable_name in ("VERCEL_BRANCH_URL", "VERCEL_URL"):
        host = os.getenv(variable_name)
        if not host:
            continue
        origin = _validate_origin(
            f"https://{host.strip().rstrip('/')}",
            source=variable_name,
        )
        origins.add(origin)
    return frozenset(origins)


def _http_base_url(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an http(s) URL")
    return value


def _path_env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    database_pooling: bool
    web_origin: str
    allowed_web_origins: frozenset[str]
    cookie_secure: bool
    session_days: int
    auth_rate_limit_attempts: int
    auth_rate_limit_minutes: int
    vin_encryption_keys: str | None
    vin_active_key_version: int
    vin_lookup_key: str | None
    provider_credential_keys: str | None
    provider_credential_active_key_version: int
    provider_ingestion_mode: str
    vin_cache_hours: int
    nhtsa_base_url: str
    nhtsa_timeout_seconds: float
    request_deadline_seconds: float
    repair_edit_lease_seconds: int
    media_root: str
    photo_max_bytes: int


def _load_settings() -> Settings:
    database_url = _database_url()

    web_origin = _web_origin()
    allowed_web_origins = _allowed_web_origins(web_origin)
    running_on_vercel = os.getenv("VERCEL") == "1"
    database_pooling = _database_pooling(running_on_vercel=running_on_vercel)
    cookie_secure = _bool_env("PARTGRAPH_COOKIE_SECURE", running_on_vercel)
    if web_origin.startswith("https://") and not cookie_secure:
        raise ValueError("PARTGRAPH_COOKIE_SECURE must be enabled for an HTTPS web origin")

    vin_encryption_keys = os.getenv("PARTGRAPH_VIN_ENCRYPTION_KEYS")
    vin_lookup_key = os.getenv("PARTGRAPH_VIN_LOOKUP_KEY")
    provider_credential_keys = os.getenv("PARTGRAPH_PROVIDER_CREDENTIAL_KEYS")
    provider_ingestion_mode = _provider_ingestion_mode()

    nhtsa_timeout_seconds = _float_env(
        "PARTGRAPH_NHTSA_TIMEOUT_SECONDS",
        DEFAULT_NHTSA_TIMEOUT_SECONDS,
        minimum=0.5,
        maximum=8.0,
    )
    request_deadline_seconds = _float_env(
        "PARTGRAPH_REQUEST_DEADLINE_SECONDS",
        DEFAULT_REQUEST_DEADLINE_SECONDS,
        minimum=1.0,
        maximum=MAX_REQUEST_DEADLINE_SECONDS,
    )
    _validate_provider_timeout_hierarchy(
        provider_timeout_seconds=nhtsa_timeout_seconds,
        request_deadline_seconds=request_deadline_seconds,
    )

    return Settings(
        database_url=database_url,
        database_pooling=database_pooling,
        web_origin=web_origin,
        allowed_web_origins=allowed_web_origins,
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
        provider_credential_keys=(
            provider_credential_keys.strip() if provider_credential_keys else None
        ),
        provider_credential_active_key_version=_int_env(
            "PARTGRAPH_PROVIDER_CREDENTIAL_ACTIVE_KEY_VERSION",
            1,
            minimum=1,
            maximum=32_767,
        ),
        provider_ingestion_mode=provider_ingestion_mode,
        vin_cache_hours=_int_env("PARTGRAPH_VIN_CACHE_HOURS", 720, minimum=1, maximum=2_160),
        nhtsa_base_url=_http_base_url(
            "PARTGRAPH_NHTSA_BASE_URL",
            "https://vpic.nhtsa.dot.gov/api/vehicles",
        ),
        nhtsa_timeout_seconds=nhtsa_timeout_seconds,
        request_deadline_seconds=request_deadline_seconds,
        repair_edit_lease_seconds=_int_env(
            "PARTGRAPH_REPAIR_EDIT_LEASE_SECONDS", 300, minimum=30, maximum=3_600
        ),
        media_root=_path_env("PARTGRAPH_MEDIA_ROOT", "/tmp/partgraph-media"),
        photo_max_bytes=_int_env(
            "PARTGRAPH_PHOTO_MAX_BYTES",
            4 * 1024 * 1024,
            minimum=1024,
            maximum=4 * 1024 * 1024,
        ),
    )


settings = _load_settings()