"""Price history service — Yahoo Finance OHLCV via yfinance."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd

from etfray.db.database import cache_price_history, get_cached_price_history

SOURCE = "yahoo"
PRICE_HISTORY_CACHE_TTL_HOURS = 24
VALID_PERIODS = frozenset({"1y", "3y", "5y", "max"})
_FETCH_RETRIES = 3
_FETCH_RETRY_DELAY_SEC = 0.75

_last_history_error: str = ""


def get_price_history_last_error() -> str:
    """Human-readable reason the most recent price history fetch failed."""
    return _last_history_error


def _set_history_error(message: str) -> None:
    global _last_history_error
    _last_history_error = message


def _clear_history_error() -> None:
    global _last_history_error
    _last_history_error = ""


def _cache_is_fresh(fetched_at: str, *, now: datetime | None = None) -> bool:
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except (ValueError, TypeError):
        return False
    current = now or datetime.now()
    return current - fetched < timedelta(hours=PRICE_HISTORY_CACHE_TTL_HOURS)


def _normalize_history_df(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    price_col = "Adj Close" if "Adj Close" in df.columns else "Close"
    if price_col not in df.columns:
        return None
    out = df.copy()
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out = out.sort_index()
    if out[price_col].dropna().empty:
        return None
    return out


def _history_from_cache(cached: dict) -> pd.DataFrame | None:
    from io import StringIO

    try:
        df = pd.read_json(StringIO(cached["history_json"]), orient="split")
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return _normalize_history_df(df)
    except (ValueError, TypeError, KeyError):
        return None


def _fetch_from_yahoo(ticker: str, period: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
    except ImportError:
        _set_history_error("yfinance is not installed (run: pip install -e '.')")
        return None

    ticker = ticker.upper()
    last_error = ""

    for attempt in range(_FETCH_RETRIES):
        try:
            df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
            normalized = _normalize_history_df(df)
            if normalized is not None:
                _clear_history_error()
                fetched_at = datetime.now().isoformat()
                cache_price_history(
                    ticker,
                    period,
                    normalized.to_json(orient="split", date_format="iso"),
                    fetched_at,
                )
                return normalized
            last_error = "Yahoo returned no price history"
        except Exception as exc:
            last_error = str(exc)
        if attempt < _FETCH_RETRIES - 1:
            time.sleep(_FETCH_RETRY_DELAY_SEC * (attempt + 1))

    _set_history_error(last_error or "Yahoo returned no price history")
    return None


def get_price_history(ticker: str, period: str = "max", *, force_refresh: bool = False) -> pd.DataFrame | None:
    """Get adjusted price history from cache or Yahoo Finance."""
    ticker = ticker.upper()
    period = period.lower()
    if period not in VALID_PERIODS:
        period = "max"

    if not force_refresh:
        cached = get_cached_price_history(ticker, period)
        if cached and _cache_is_fresh(cached["fetched_at"]):
            df = _history_from_cache(cached)
            if df is not None:
                _clear_history_error()
                return df

    return _fetch_from_yahoo(ticker, period)
