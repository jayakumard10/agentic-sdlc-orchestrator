"""Unit tests for app.main._generate_unique_code's collision-retry logic,

independent of the HTTP/database layers.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.main import _generate_unique_code


class _FakeRepo:
    """Minimal URLRepository stand-in: code_exists returns True for the first

    `collisions` calls, then False.
    """

    def __init__(self, collisions: int) -> None:
        self._collisions = collisions
        self._calls = 0

    def code_exists(self, code: str) -> bool:
        self._calls += 1
        return self._calls <= self._collisions


def test_generate_unique_code_succeeds_on_first_try_with_no_collisions():
    repo = _FakeRepo(collisions=0)
    code = _generate_unique_code(repo)
    assert len(code) == 7
    assert repo._calls == 1


def test_generate_unique_code_retries_past_collisions():
    repo = _FakeRepo(collisions=3)
    code = _generate_unique_code(repo)
    assert len(code) == 7
    assert repo._calls == 4


def test_generate_unique_code_gives_up_after_max_attempts():
    repo = _FakeRepo(collisions=999)
    with pytest.raises(HTTPException) as exc_info:
        _generate_unique_code(repo)
    assert exc_info.value.status_code == 500
