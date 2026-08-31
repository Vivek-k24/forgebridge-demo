import json
from pathlib import Path

from partgraph import config


def test_managed_database_url_falls_back_to_standard_database_url(monkeypatch) -> None:
    monkeypatch.delenv("PARTGRAPH_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:secret@example.neon.tech/neondb?sslmode=require",
    )

    assert config._database_url() == (
        "postgresql+psycopg://user:secret@example.neon.tech/neondb?sslmode=require"
    )


def test_partgraph_database_url_remains_authoritative(monkeypatch) -> None:
    monkeypatch.setenv(
        "PARTGRAPH_DATABASE_URL",
        "postgresql+psycopg://partgraph:partgraph@db:5432/partgraph",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:secret@example.neon.tech/neondb?sslmode=require",
    )

    assert config._database_url() == (
        "postgresql+psycopg://partgraph:partgraph@db:5432/partgraph"
    )


def test_legacy_postgres_scheme_is_normalized_for_psycopg(monkeypatch) -> None:
    monkeypatch.delenv("PARTGRAPH_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://user:secret@host/database")

    assert config._database_url() == "postgresql+psycopg://user:secret@host/database"


def test_web_origin_uses_vercel_production_domain_when_not_explicit(monkeypatch) -> None:
    monkeypatch.delenv("PARTGRAPH_WEB_ORIGIN", raising=False)
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "partgraph-main.vercel.app")

    assert config._web_origin() == "https://partgraph-main.vercel.app"


def test_explicit_web_origin_overrides_vercel_domain(monkeypatch) -> None:
    monkeypatch.setenv("PARTGRAPH_WEB_ORIGIN", "https://partgraph.example.com/")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "partgraph-main.vercel.app")

    assert config._web_origin() == "https://partgraph.example.com"


def test_local_web_origin_remains_default_without_vercel(monkeypatch) -> None:
    monkeypatch.delenv("PARTGRAPH_WEB_ORIGIN", raising=False)
    monkeypatch.delenv("VERCEL_PROJECT_PRODUCTION_URL", raising=False)

    assert config._web_origin() == "http://localhost:5173"


def test_vercel_defaults_session_cookie_to_secure(monkeypatch) -> None:
    monkeypatch.delenv("PARTGRAPH_WEB_ORIGIN", raising=False)
    monkeypatch.delenv("PARTGRAPH_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "partgraph-main.vercel.app")

    settings = config._load_settings()

    assert settings.web_origin == "https://partgraph-main.vercel.app"
    assert settings.cookie_secure is True


def test_explicit_insecure_cookie_is_still_rejected_on_vercel(monkeypatch) -> None:
    monkeypatch.delenv("PARTGRAPH_WEB_ORIGIN", raising=False)
    monkeypatch.setenv("PARTGRAPH_COOKIE_SECURE", "false")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "partgraph-main.vercel.app")

    try:
        config._load_settings()
    except ValueError as exc:
        assert str(exc) == "PARTGRAPH_COOKIE_SECURE must be enabled for an HTTPS web origin"
    else:
        raise AssertionError("Vercel HTTPS origin accepted an explicitly insecure cookie")


def test_vercel_uses_single_fastapi_framework_entrypoint() -> None:
    config_path = Path(__file__).resolve().parents[1] / "vercel.json"
    deployment_config = json.loads(config_path.read_text(encoding="utf-8"))

    assert deployment_config["framework"] == "fastapi"
    assert deployment_config["regions"] == ["iad1"]
    assert deployment_config["functions"] == {"partgraph/main.py": {"maxDuration": 60}}
