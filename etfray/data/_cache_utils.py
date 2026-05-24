"""Shared caching and retry utilities for data services."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, TypeVar

_log = logging.getLogger(__name__)

T = TypeVar("T")


def cache_is_fresh(fetched_at: str, *, ttl: timedelta, now: datetime | None = None) -> bool:
    """Return True when fetched_at is within ttl of now."""
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except (ValueError, TypeError):
        return False
    current = now or datetime.now()
    return current - fetched < ttl


def retry_fetch(
    fn: Callable[[], T | None],
    *,
    retries: int = 3,
    delay_sec: float = 0.75,
) -> T | None:
    """Call fn() up to retries times with linear backoff, returning the first non-None result.

    On each failed attempt (fn returns None or raises), waits delay_sec * attempt seconds
    before retrying. Returns None if all attempts fail.
    """
    last_result = None
    for attempt in range(retries):
        try:
            result = fn()
            if result is not None:
                return result
            last_result = result
        except Exception as exc:
            _log.warning("retry_fetch attempt %d failed: %s", attempt + 1, exc)
        if attempt < retries - 1:
            time.sleep(delay_sec * (attempt + 1))
    return last_result
