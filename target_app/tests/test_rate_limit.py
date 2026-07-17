"""Unit tests for app.rate_limit's fixed-window limiter, independent of the HTTP layer."""

from __future__ import annotations

import pytest

from app import rate_limit


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    rate_limit.reset()
    yield
    rate_limit.reset()


def test_allows_requests_up_to_the_window_limit():
    for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
        assert rate_limit.is_allowed("client-a") is True


def test_blocks_request_beyond_the_window_limit():
    for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
        rate_limit.is_allowed("client-a")
    assert rate_limit.is_allowed("client-a") is False


def test_different_clients_are_tracked_independently():
    for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
        rate_limit.is_allowed("client-a")
    assert rate_limit.is_allowed("client-a") is False
    assert rate_limit.is_allowed("client-b") is True


def test_requests_allowed_again_after_the_window_expires(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: fake_time[0])

    for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
        rate_limit.is_allowed("client-a")
    assert rate_limit.is_allowed("client-a") is False

    fake_time[0] += rate_limit.WINDOW_SECONDS + 1
    assert rate_limit.is_allowed("client-a") is True


def test_reset_clears_all_client_state():
    for _ in range(rate_limit.MAX_REQUESTS_PER_WINDOW):
        rate_limit.is_allowed("client-a")
    rate_limit.reset()
    assert rate_limit.is_allowed("client-a") is True
