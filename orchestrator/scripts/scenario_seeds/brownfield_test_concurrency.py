"""Regression test for the reported click-counter undercount bug: verifies

increment_click is correct under real concurrent access.

Runs against PostgreSQL specifically, not the in-memory SQLite the rest of the test
suite uses - SQLite serializes writes at the connection level, which does not
reproduce the same lost-update race a real MVCC database exhibits under concurrent
transactions. Testing a concurrency bug against a database whose concurrency model
differs from production would validate nothing. Skipped (not failed) if Postgres
isn't reachable, matching this project's SQLite-fallback philosophy for
environments without Docker/Postgres available.

This file represents a QA-authored regression test that already exists in the
codebase when the bug report comes in - the brownfield scenario is "make this
failing test pass," not "notice there might be a race condition."
"""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.repository import SQLAlchemyURLRepository

CONCURRENT_INCREMENTS = 50


def _postgres_url() -> str | None:
    explicit = os.environ.get("DATABASE_URL")
    if explicit and explicit.startswith("postgresql"):
        return explicit
    user = os.environ.get("POSTGRES_USER")
    if not user:
        return None
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "orchestrator")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def _postgres_reachable(url: str) -> bool:
    try:
        connection = create_engine(url).connect()
        connection.close()
        return True
    except OperationalError:
        return False


_DATABASE_URL = _postgres_url()
_SKIP_REASON = "requires a reachable PostgreSQL instance (DATABASE_URL or POSTGRES_* env vars)"
_AVAILABLE = _DATABASE_URL is not None and _postgres_reachable(_DATABASE_URL)


@pytest.mark.skipif(not _AVAILABLE, reason=_SKIP_REASON)
def test_increment_click_is_correct_under_concurrent_access():
    engine = create_engine(_DATABASE_URL, pool_size=20, max_overflow=0)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    code = f"race-{secrets.token_hex(4)}"
    setup_repo = SQLAlchemyURLRepository(session_factory())
    setup_repo.create(code=code, long_url="https://example.com")

    def do_increment() -> None:
        repo = SQLAlchemyURLRepository(session_factory())
        repo.increment_click(code)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(lambda _: do_increment(), range(CONCURRENT_INCREMENTS)))

    verify_repo = SQLAlchemyURLRepository(session_factory())
    record = verify_repo.get_by_code(code)
    assert record is not None
    assert record.click_count == CONCURRENT_INCREMENTS
