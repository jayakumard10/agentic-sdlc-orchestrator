"""Integration tests for the URL shortener's HTTP API."""

from __future__ import annotations

from app.rate_limit import MAX_REQUESTS_PER_WINDOW


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shorten_then_redirect_then_stats(client):
    shorten_response = client.post("/shorten", json={"long_url": "https://example.com/some/page"})
    assert shorten_response.status_code == 201
    body = shorten_response.json()
    code = body["code"]
    assert body["long_url"] == "https://example.com/some/page"

    redirect_response = client.get(f"/{code}", follow_redirects=False)
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == "https://example.com/some/page"

    stats_response = client.get(f"/{code}/stats")
    assert stats_response.status_code == 200
    stats_body = stats_response.json()
    assert stats_body["click_count"] == 1
    assert stats_body["code"] == code


def test_redirect_unknown_code_returns_404(client):
    response = client.get("/doesnotexist")
    assert response.status_code == 404


def test_stats_unknown_code_returns_404(client):
    response = client.get("/doesnotexist/stats")
    assert response.status_code == 404


def test_shorten_rejects_invalid_url(client):
    response = client.post("/shorten", json={"long_url": "not-a-url"})
    assert response.status_code == 422


def test_shorten_rate_limit_enforced(client):
    for _ in range(MAX_REQUESTS_PER_WINDOW):
        response = client.post("/shorten", json={"long_url": "https://example.com/x"})
        assert response.status_code == 201
    limited_response = client.post("/shorten", json={"long_url": "https://example.com/x"})
    assert limited_response.status_code == 429
