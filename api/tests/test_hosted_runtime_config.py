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
