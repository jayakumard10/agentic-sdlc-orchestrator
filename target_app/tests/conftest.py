"""Shared test fixtures: an isolated in-memory SQLite database per test, with the

app's real init_db() neutralized so tests never touch the production DATABASE_URL.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import rate_limit
from app.db import Base, get_session
from app.main import app

TEST_API_KEY = "test-api-key"


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(test_engine, monkeypatch):
    testing_session_local = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_session():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.setattr("app.main.init_db", lambda: None)
    app.dependency_overrides[get_session] = override_get_session
    rate_limit.reset()
    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": TEST_API_KEY})
        yield test_client
    app.dependency_overrides.clear()
