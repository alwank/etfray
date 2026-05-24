"""Price history service — Yahoo Finance OHLCV via yfinance."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd

from etfray.data._cache_utils import cache_is_fresh
from etfray.db.database import cache_price_history, get_cached_price_history

SOURCE = "yahoo"
PRICE_HISTORY_CACHE_TTL_HOURS = 24
VALID_PERIODS = frozenset({"1y", "3y", "5y", "max"})
_FETCH_RETRIES = 3
_FETCH_RETRY_DELAY_SEC = 0.75


def _normalize_history_df(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    # auto_adjust=True: Yahoo returns adjusted prices in 'Close'; 'Adj Close' is not present.
    price_col = "Close"
    if price_col not in df.columns:
        return None
    out = df.copy()
    if out.index.tz is not None:
        out.index = out.index.tz_convert("UTC").tz_localize(None)
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


def _fetch_from_yahoo(ticker: str, period: str) -> tuple[pd.DataFrame | None, str]:
    try:
        import yfinance as yf
    except ImportError:
        return None, "yfinance is not installed (run: pip install -e '.')"

    ticker = ticker.upper()
    last_error = ""

    for attempt in range(_FETCH_RETRIES):
        try:
            df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
            normalized = _normalize_history_df(df)
            if normalized is not None:
                fetched_at = datetime.now().isoformat()
                cache_price_history(
                    ticker,
                    period,
                    normalized.to_json(orient="split", date_format="iso"),
                    fetched_at,
                )
                return normalized, ""
            last_error = "Yahoo returned no price history"
        except Exception as exc:
            last_error = str(exc)
        if attempt < _FETCH_RETRIES - 1:
            time.sleep(_FETCH_RETRY_DELAY_SEC * (attempt + 1))

    return None, last_error or "Yahoo returned no price history"


def get_price_history(ticker: str, period: str = "max", *, force_refresh: bool = False) -> tuple[pd.DataFrame | None, str]:
    """Get adjusted price history from cache or Yahoo Finance.

    Returns a ``(dataframe, error)`` tuple.  On success the error string is empty.
    """
    ticker = ticker.upper()
    period = period.lower()
    if period not in VALID_PERIODS:
        period = "max"

    if not force_refresh:
        cached = get_cached_price_history(ticker, period)
        if cached and cache_is_fresh(cached["fetched_at"], ttl=timedelta(hours=PRICE_HISTORY_CACHE_TTL_HOURS)):
            df = _history_from_cache(cached)
            if df is not None:
                return df, ""

    return _fetch_from_yahoo(ticker, period)
