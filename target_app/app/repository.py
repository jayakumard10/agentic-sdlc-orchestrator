"""Repository/DAO layer sitting between the API and the database.

increment_click is deliberately a read-modify-write against the ORM object rather
than a single atomic UPDATE statement - this is the target-app codebase's starting
state, and its latent lost-update race condition under concurrent redirects is
exactly the bug the brownfield demo scenario fixes.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from app.models import ShortURL


class URLRepository(Protocol):
    def create(self, code: str, long_url: str) -> ShortURL: ...

    def get_by_code(self, code: str) -> ShortURL | None: ...

    def increment_click(self, code: str) -> None: ...

    def code_exists(self, code: str) -> bool: ...


class SQLAlchemyURLRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, code: str, long_url: str) -> ShortURL:
        record = ShortURL(code=code, long_url=long_url, click_count=0)
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def get_by_code(self, code: str) -> ShortURL | None:
        return self._session.query(ShortURL).filter_by(code=code).first()

    def increment_click(self, code: str) -> None:
        record = self._session.query(ShortURL).filter_by(code=code).first()
        if record is None:
            return
        record.click_count = record.click_count + 1
        self._session.commit()

    def code_exists(self, code: str) -> bool:
        return self._session.query(ShortURL).filter_by(code=code).first() is not None
