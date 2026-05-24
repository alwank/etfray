"""Screener service — ETF day gainers/losers via yfinance screener + seed universe."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from etfray.db.database import cache_screener_result, get_cached_screener_result

SCREENER_CACHE_TTL_HOURS = 1
_CACHE_KEY_MOVERS = "etf_movers"
_FETCH_SIZE = 50  # quotes to request per screener query
_TOP_N = 5  # gainers / losers to surface in the UI
_STALE_HOURS = 24  # if regularMarketTime is older than this, data is stale
_SEED_MIN = _TOP_N * 2  # minimum ETF pool size before triggering seed fallback

# Market-wide screeners that reliably include high-volume ETFs (SPY, QQQ, sector ETFs, etc.)
_SCREENER_QUERIES = ["most_actives", "gainers", "losers"]

# Hardcoded seed universe covering broad equity, fixed income, commodities,
# international, and sector ETFs — used as Tier-2 fallback when the screener
# pool contains too few ETFs (e.g. outside market hours or API changes).
_SEED_TICKERS = [
    # Broad equity
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "VTI",
    "IVV",
    "VOO",
    # Factor / style
    "VUG",
    "VTV",
    "IJR",
    "MTUM",
    # Fixed income
    "TLT",
    "AGG",
    "HYG",
    "LQD",
    "SHY",
    "BND",
    # Commodities
    "GLD",
    "SLV",
    "USO",
    "IAU",
    # International
    "EEM",
    "EFA",
    "VEA",
    "VWO",
    # Sectors
    "XLF",
    "XLK",
    "XLE",
    "XLV",
    "XLI",
    "XLY",
    "XLB",
    "XLU",
    "XLC",
    "XLRE",
    # Leveraged (high day-change, makes movers interesting)
    "TQQQ",
    "SQQQ",
    "UPRO",
    "SPXU",
]

_last_screener_error: str = ""


@dataclass
class ETFMover:
    symbol: str
    name: str
    change_pct: float | None  # decimal fraction (0.042 = +4.2 %); None when data is missing
    last_trade_ts: int | None  # Unix epoch seconds from regularMarketTime


@dataclass
class ETFMovers:
    gainers: list[ETFMover]
    losers: list[ETFMover]
    fetched_at: str  # ISO datetime
    is_stale: bool  # True when the most recent trade is > _STALE_HOURS old


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
            change_pct: float | None = float(pct_raw) / 100 if pct_raw is not None else None
        except (TypeError, ValueError):
            change_pct = None
        ts_raw = q.get("regularMarketTime")
        try:
            last_trade_ts = int(ts_raw) if ts_raw is not None else None
        except (TypeError, ValueError):
            last_trade_ts = None
        movers.append(ETFMover(symbol=symbol, name=name, change_pct=change_pct, last_trade_ts=last_trade_ts))
    return movers


def _fetch_seed_universe(yf) -> list[dict]:
    """Fetch the last two days of prices for the seed ticker list and return
    quote-like dicts with ``regularMarketChangePercent`` and ``last_trade_ts``.

    Uses ``yf.download()`` in batch mode (single HTTP round-trip) so the cost
    is low even for ~40 tickers.  Returns an empty list on any error.
    """
    try:
        df = yf.download(
            tickers=_SEED_TICKERS,
            period="5d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if df is None or df.empty:
            return []

        # yf.download with multiple tickers returns a MultiIndex (field, ticker)
        close = df["Close"] if "Close" in df.columns else None
        if close is None:
            return []

        # Drop rows that are entirely NaN then take the last two non-NaN rows
        close = close.dropna(how="all").tail(2)
        if len(close) < 2:
            return []

        prev_row = close.iloc[-2]
        last_row = close.iloc[-1]

        # Approximate last_trade_ts from the index of the last row
        try:
            ts = int(last_row.name.timestamp())
        except Exception:
            ts = None

        quotes: list[dict] = []
        for ticker in _SEED_TICKERS:
            if ticker not in last_row.index:
                continue
            prev = prev_row.get(ticker)
            last = last_row.get(ticker)
            if prev is None or last is None:
                continue
            try:
                prev_f = float(prev)
                last_f = float(last)
            except (TypeError, ValueError):
                continue
            if prev_f == 0:
                continue
            day_pct = (last_f - prev_f) / prev_f * 100
            quotes.append(
                {
                    "symbol": ticker,
                    "longName": ticker,
                    "quoteType": "ETF",
                    "regularMarketChangePercent": day_pct,
                    "regularMarketTime": ts,
                }
            )
        return quotes
    except Exception:
        return []


def _fetch_from_yahoo() -> ETFMovers | None:
    """Fetch ETF movers from Yahoo Finance screener with seed-universe fallback."""
    try:
        import yfinance as yf
    except ImportError:
        _set_screener_error("yfinance is not installed (run: pip install -e '.')")
        return None

    # ── Tier 1: market-wide screeners ──────────────────────────────────────
    # These queries (most_actives, gainers, losers) include high-volume ETFs
    # such as SPY, QQQ, IWM and sector ETFs alongside stocks.
    all_quotes: list[dict] = []

    for query_name in _SCREENER_QUERIES:
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

    # De-duplicate by symbol, keeping first occurrence
    seen: set[str] = set()
    unique_quotes: list[dict] = []
    for q in all_quotes:
        sym = str(q.get("symbol") or "").strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            unique_quotes.append(q)

    # Filter to ETFs only — quoteType == "ETF" for exchange-traded funds
    etf_quotes = [q for q in unique_quotes if str(q.get("quoteType") or "").upper() == "ETF"]

    # ── Tier 2: seed-universe fallback ────────────────────────────────────
    # When the screener returns fewer than _SEED_MIN ETFs (e.g. outside market
    # hours, API changes, or rate-limiting), supplement with a batch download
    # of well-known ETFs so the panel always shows meaningful data.
    if len(etf_quotes) < _SEED_MIN:
        seed_quotes = _fetch_seed_universe(yf)
        # Merge seed quotes that aren't already in the screener pool
        seed_seen = {str(q.get("symbol") or "").strip().upper() for q in etf_quotes}
        for q in seed_quotes:
            sym = str(q.get("symbol") or "").strip().upper()
            if sym and sym not in seed_seen:
                seed_seen.add(sym)
                etf_quotes.append(q)

    if not etf_quotes:
        _set_screener_error("No ETF quotes returned from screener or seed universe")
        return None

    # Exclude quotes with missing regularMarketChangePercent before sorting
    def _has_pct(q: dict) -> bool:
        try:
            v = q.get("regularMarketChangePercent")
            if v is None:
                return False
            float(v)
            return True
        except (TypeError, ValueError):
            return False

    etf_quotes_with_pct = [q for q in etf_quotes if _has_pct(q)]
    sortable = etf_quotes_with_pct if etf_quotes_with_pct else etf_quotes

    # Sort by day change to find gainers (desc) and losers (asc)
    def _pct(q: dict) -> float:
        try:
            return float(q.get("regularMarketChangePercent") or 0)
        except (TypeError, ValueError):
            return 0.0

    sorted_desc = sorted(sortable, key=_pct, reverse=True)
    sorted_asc = sorted(sortable, key=_pct)

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
