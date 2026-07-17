"""In-process fixed-window rate limiter guarding POST /shorten (the reliability feature

named in scope). Deliberately simple - no Redis, no distributed state - since a
single-container demo has no multi-instance concurrency to coordinate across.
"""

from __future__ import annotations

import time
from collections import defaultdict

WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 30

_hits: dict[str, list[float]] = defaultdict(list)


def is_allowed(client_key: str) -> bool:
    now = time.monotonic()
    window_start = now - WINDOW_SECONDS
    hits = _hits[client_key]
    while hits and hits[0] < window_start:
        hits.pop(0)
    if len(hits) >= MAX_REQUESTS_PER_WINDOW:
        return False
    hits.append(now)
    return True


def reset() -> None:
    """Test-only: clear all rate-limit state between test cases."""
    _hits.clear()
