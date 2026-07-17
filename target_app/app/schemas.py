"""Pydantic request/response schemas for the URL shortener API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class ShortenRequest(BaseModel):
    long_url: HttpUrl


class ShortenResponse(BaseModel):
    code: str
    short_url: str
    long_url: str


class StatsResponse(BaseModel):
    code: str
    long_url: str
    click_count: int
    created_at: datetime
