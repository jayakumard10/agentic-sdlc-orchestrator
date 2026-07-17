"""Database engine/session setup: PostgreSQL by default, SQLite fallback behind the

same interface if POSTGRES_* environment variables aren't set (e.g. running without
Docker). No Alembic - Base.metadata.create_all() on startup is the documented,
deliberate "would add for production" gap.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit
    user = os.environ.get("POSTGRES_USER")
    if not user:
        return "sqlite:///./url_shortener.db"
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "orchestrator")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


_DATABASE_URL = _database_url()
_CONNECT_ARGS = {"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(_DATABASE_URL, connect_args=_CONNECT_ARGS)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
