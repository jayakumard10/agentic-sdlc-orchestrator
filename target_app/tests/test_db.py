"""Unit tests for app.db's connection-string construction logic."""

from __future__ import annotations

from app.db import _database_url


def test_database_url_defaults_to_sqlite_without_postgres_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    assert _database_url() == "sqlite:///./url_shortener.db"


def test_database_url_uses_explicit_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://custom/override")
    assert _database_url() == "postgresql+psycopg://custom/override"


def test_database_url_builds_from_postgres_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "orchestrator")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_HOST", "db-host")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "mydb")
    assert _database_url() == "postgresql+psycopg://orchestrator:secret@db-host:5433/mydb"


def test_database_url_uses_defaults_for_optional_postgres_fields(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "orchestrator")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    assert _database_url() == "postgresql+psycopg://orchestrator:@postgres:5432/orchestrator"
