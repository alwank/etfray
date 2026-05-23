"""Screener service — ETF day gainers/losers via yfinance FundQuery screener."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from etfray.db.database import cache_screener_result, get_cached_screener_result

SCREENER_CACHE_TTL_HOURS = 1
_CACHE_KEY_MOVERS = "etf_movers"
_FETCH_SIZE = 30          # fetch this many from each pool, then filter to ETFs
_TOP_N = 5                # gainers / losers to surface in the UI
_STALE_HOURS = 24         # if regularMarketTime is older than this, data is stale

_last_screener_error: str = ""


@dataclass
class ETFMover:
    symbol: str
    name: str
    change_pct: float          # decimal fraction (0.042 = +4.2 %)
    last_trade_ts: int | None  # Unix epoch seconds from regularMarketTime


@dataclass
class ETFMovers:
    gainers: list[ETFMover]
    losers: list[ETFMover]
    fetched_at: str            # ISO datetime
    is_stale: bool             # True when the most recent trade is > _STALE_HOURS old


def get_screener_last_error() -> str:
    """Human-readable reason the most recent screener fetch failed."""
    return _last_screener_error


def _set_screener_error(message: str) -> None:
    global _last_screener_error
    _last_screener_error = message


def _clear_screener_error() -> None:
    global _last_screener_error
    _last_screener_error = ""


def _cache_is_fresh(fetched_at: str, *, now: datetime | None = None) -> bool:
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except (ValueError, TypeError):
        return False
    current = now or datetime.now()
    return current - fetched < timedelta(hours=SCREENER_CACHE_TTL_HOURS)


def _is_stale_market_data(quotes: list[dict]) -> bool:
    """Return True if the most recent regularMarketTime in quotes is > _STALE_HOURS old."""
    now_utc = datetime.now(tz=timezone.utc).timestamp()
    for q in quotes:
        ts = q.get("regularMarketTime")
        if ts is not None:
            try:
                age_hours = (now_utc - int(ts)) / 3600
                if age_hours <= _STALE_HOURS:
                    return False
            except (TypeError, ValueError):
                pass
    return True


def _quotes_to_movers(quotes: list[dict]) -> list[ETFMover]:
    movers: list[ETFMover] = []
    for q in quotes:
        if not isinstance(q, dict):
            continue
        symbol = str(q.get("symbol") or "").strip()
        if not symbol:
            continue
        name = str(q.get("longName") or q.get("shortName") or symbol).strip()
        pct_raw = q.get("regularMarketChangePercent")
        try:
            change_pct = float(pct_raw) / 100 if pct_raw is not None else 0.0
        except (TypeError, ValueError):
            change_pct = 0.0
        ts_raw = q.get("regularMarketTime")
        try:
            last_trade_ts = int(ts_raw) if ts_raw is not None else None
        except (TypeError, ValueError):
            last_trade_ts = None
        movers.append(ETFMover(symbol=symbol, name=name, change_pct=change_pct, last_trade_ts=last_trade_ts))
    return movers


def _fetch_from_yahoo() -> ETFMovers | None:
    """Fetch ETF movers from Yahoo Finance screener and write through to cache."""
    try:
        import yfinance as yf
    except ImportError:
        _set_screener_error("yfinance is not installed (run: pip install -e '.')")
        return None

    # Use the 5 fund-oriented predefined queries as candidate pools.
    # None of Yahoo's predefined queries are ETF-only, so we filter by quoteType after fetch.
    fund_queries = [
        "conservative_foreign_funds",
        "high_yield_bond",
        "portfolio_anchors",
        "solid_large_growth_funds",
        "solid_midcap_growth_funds",
    ]

    all_quotes: list[dict] = []

    for query_name in fund_queries:
        try:
            result = yf.screen(query_name, count=_FETCH_SIZE)
            if isinstance(result, dict):
                quotes = result.get("quotes") or []
            elif isinstance(result, list):
                quotes = result
            else:
                quotes = []
            all_quotes.extend(q for q in quotes if isinstance(q, dict))
        except Exception as exc:
            _set_screener_error(f"screener fetch error ({query_name}): {exc}")
            time.sleep(0.5)
            continue

    if not all_quotes:
        _set_screener_error("Yahoo screener returned no results")
        return None

    # De-duplicate by symbol, keeping first occurrence
    seen: set[str] = set()
    unique_quotes: list[dict] = []
    for q in all_quotes:
        sym = str(q.get("symbol") or "").strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            unique_quotes.append(q)

    # Filter to ETFs only — quoteType field is "ETF" for exchange-traded funds
    etf_quotes = [
        q for q in unique_quotes
        if str(q.get("quoteType") or "").upper() == "ETF"
    ]

    if not etf_quotes:
        # Fallback: accept any fund-type quote when the pool is too small
        etf_quotes = unique_quotes

    # Sort by day change to find gainers (desc) and losers (asc)
    def _pct(q: dict) -> float:
        try:
            return float(q.get("regularMarketChangePercent") or 0)
        except (TypeError, ValueError):
            return 0.0

    sorted_desc = sorted(etf_quotes, key=_pct, reverse=True)
    sorted_asc = sorted(etf_quotes, key=_pct)

    gainers = _quotes_to_movers(sorted_desc[:_TOP_N])
    losers = _quotes_to_movers(sorted_asc[:_TOP_N])

    is_stale = _is_stale_market_data(etf_quotes)
    fetched_at = datetime.now().isoformat()

    payload = {
        "gainers": [
            {"symbol": m.symbol, "name": m.name, "change_pct": m.change_pct, "last_trade_ts": m.last_trade_ts}
            for m in gainers
        ],
        "losers": [
            {"symbol": m.symbol, "name": m.name, "change_pct": m.change_pct, "last_trade_ts": m.last_trade_ts}
            for m in losers
        ],
        "fetched_at": fetched_at,
        "is_stale": is_stale,
    }

    _clear_screener_error()
    cache_screener_result(_CACHE_KEY_MOVERS, json.dumps(payload), fetched_at)

    return ETFMovers(gainers=gainers, losers=losers, fetched_at=fetched_at, is_stale=is_stale)


def _movers_from_cache(cached: dict) -> ETFMovers | None:
    try:
        data = json.loads(cached["result_json"])
        gainers = [ETFMover(**m) for m in data.get("gainers", [])]
        losers = [ETFMover(**m) for m in data.get("losers", [])]
        return ETFMovers(
            gainers=gainers,
            losers=losers,
            fetched_at=data.get("fetched_at", ""),
            is_stale=bool(data.get("is_stale", False)),
        )
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def get_etf_movers(*, force_refresh: bool = False) -> ETFMovers | None:
    """Return top ETF gainers and losers — cache-first, 1-hour TTL."""
    if not force_refresh:
        cached = get_cached_screener_result(_CACHE_KEY_MOVERS)
        if cached and _cache_is_fresh(cached["fetched_at"]):
            movers = _movers_from_cache(cached)
            if movers is not None:
                _clear_screener_error()
                return movers

    return _fetch_from_yahoo()
