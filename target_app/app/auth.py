"""Lightweight API-key auth: a single shared secret required on write/analytics

endpoints. Not full user auth (see docs/architecture.md for that trade-off) - this
guards against the two concrete abuse vectors in scope: anonymous link creation and
anyone enumerating codes to read another link's click analytics. The redirect
endpoint itself (GET /{code}) stays public - that's the actual recipient-facing
flow a URL shortener exists for, and it must not require a key.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException

_DEV_DEFAULT_API_KEY = "dev-local-api-key"


def _configured_api_key() -> str:
    return os.environ.get("API_KEY", _DEV_DEFAULT_API_KEY)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key is None or x_api_key != _configured_api_key():
        raise HTTPException(status_code=401, detail="invalid or missing API key")
