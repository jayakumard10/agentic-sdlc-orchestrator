"""Unit tests for the repository layer, independent of the HTTP API."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.repository import SQLAlchemyURLRepository


def _make_repo() -> SQLAlchemyURLRepository:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    return SQLAlchemyURLRepository(session)


def test_create_and_get_by_code():
    repo = _make_repo()
    record = repo.create(code="abc1234", long_url="https://example.com")
    assert record.click_count == 0
    fetched = repo.get_by_code("abc1234")
    assert fetched is not None
    assert fetched.long_url == "https://example.com"


def test_get_by_code_missing_returns_none():
    repo = _make_repo()
    assert repo.get_by_code("missing") is None


def test_increment_click_increases_count():
    repo = _make_repo()
    repo.create(code="abc1234", long_url="https://example.com")
    repo.increment_click("abc1234")
    repo.increment_click("abc1234")
    fetched = repo.get_by_code("abc1234")
    assert fetched is not None
    assert fetched.click_count == 2


def test_increment_click_missing_code_is_noop():
    repo = _make_repo()
    repo.increment_click("missing")


def test_code_exists():
    repo = _make_repo()
    assert repo.code_exists("abc1234") is False
    repo.create(code="abc1234", long_url="https://example.com")
    assert repo.code_exists("abc1234") is True
