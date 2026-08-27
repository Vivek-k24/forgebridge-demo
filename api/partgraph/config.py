from dataclasses import dataclass
from os import getenv


def _bool_env(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = getenv(
        "PARTGRAPH_DATABASE_URL",
        "postgresql+psycopg://partgraph:partgraph@localhost:5432/partgraph",
    )
    web_origin: str = getenv("PARTGRAPH_WEB_ORIGIN", "http://localhost:5173")
    cookie_secure: bool = _bool_env("PARTGRAPH_COOKIE_SECURE", False)
    session_days: int = int(getenv("PARTGRAPH_SESSION_DAYS", "30"))
    auth_rate_limit_attempts: int = int(getenv("PARTGRAPH_AUTH_RATE_LIMIT_ATTEMPTS", "10"))
    auth_rate_limit_minutes: int = int(getenv("PARTGRAPH_AUTH_RATE_LIMIT_MINUTES", "15"))


settings = Settings()
