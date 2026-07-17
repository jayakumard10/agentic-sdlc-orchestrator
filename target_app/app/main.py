"""FastAPI entry point: the URL shortener's core APIs, analytics, and reliability feature."""

from __future__ import annotations

import secrets
import string
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import rate_limit
from app.auth import require_api_key
from app.db import get_session, init_db
from app.repository import SQLAlchemyURLRepository, URLRepository
from app.schemas import ShortenRequest, ShortenResponse, StatsResponse

_CODE_ALPHABET = string.ascii_letters + string.digits
_CODE_LENGTH = 7
_MAX_CODE_GENERATION_ATTEMPTS = 10


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)


def get_repository(session: Session = Depends(get_session)) -> URLRepository:
    return SQLAlchemyURLRepository(session)


def _generate_unique_code(repo: URLRepository) -> str:
    for _ in range(_MAX_CODE_GENERATION_ATTEMPTS):
        candidate = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        if not repo.code_exists(candidate):
            return candidate
    raise HTTPException(status_code=500, detail="failed to generate a unique short code")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
def shorten(
    payload: ShortenRequest,
    request: Request,
    repo: URLRepository = Depends(get_repository),
) -> ShortenResponse:
    client_key = request.client.host if request.client else "unknown"
    if not rate_limit.is_allowed(client_key):
        raise HTTPException(status_code=429, detail="rate limit exceeded, try again later")

    code = _generate_unique_code(repo)
    long_url = str(payload.long_url)
    repo.create(code=code, long_url=long_url)
    return ShortenResponse(code=code, short_url=f"/{code}", long_url=long_url)


@app.get(
    "/{code}/stats",
    response_model=StatsResponse,
    dependencies=[Depends(require_api_key)],
)
def stats(code: str, repo: URLRepository = Depends(get_repository)) -> StatsResponse:
    record = repo.get_by_code(code)
    if record is None:
        raise HTTPException(status_code=404, detail="short URL not found")
    return StatsResponse(
        code=record.code,
        long_url=record.long_url,
        click_count=record.click_count,
        created_at=record.created_at,
    )


@app.get("/{code}")
def redirect(code: str, repo: URLRepository = Depends(get_repository)) -> RedirectResponse:
    record = repo.get_by_code(code)
    if record is None:
        raise HTTPException(status_code=404, detail="short URL not found")
    repo.increment_click(code)
    return RedirectResponse(url=record.long_url, status_code=307)
