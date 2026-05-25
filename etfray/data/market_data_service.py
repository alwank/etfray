"""Market data service — Yahoo Finance profile metadata via yfinance."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from etfray.data._cache_utils import cache_is_fresh, retry_fetch  # noqa: F401
from etfray.db.database import cache_etf_profile, get_cached_etf_profile

if TYPE_CHECKING:
    from etfray.data.edgar_service import ETFUniverseEntry

PROFILE_CACHE_TTL_DAYS = 7
SOURCE = "yahoo"
_FETCH_RETRIES = 3
_FETCH_RETRY_DELAY_SEC = 0.75


@dataclass
class ETFProfile:
    ticker: str
    long_name: str = ""
    short_name: str = ""
    description: str = ""
    category: str = ""
    fund_family: str = ""
    inception_date: str = ""
    expense_ratio: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    ytd_return: float | None = None
    return_3y: float | None = None
    return_5y: float | None = None
    total_assets: float | None = None
    exchange: str = ""
    avg_volume: float | None = None
    nav_price: float | None = None
    legal_type: str = ""
    num_holdings: int | None = None
    source: str = SOURCE
    fetched_at: str = ""


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_inception_date(value) -> str:
    if value is None:
        return ""
    try:
        ts = int(value)
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return str(value) if value else ""


def _normalize_expense_ratio(value) -> float | None:
    """Normalize Yahoo expense ratio to decimal fraction (0.0003 = 0.03%)."""
    v = _safe_float(value)
    if v is None:
        return None
    # Yahoo almost always returns a decimal fraction (0.0075 = 0.75%).
    # Only divide by 100 when the value is clearly a whole-percent number (>= 1),
    # e.g. Yahoo returns 75 meaning 0.75% — needs /100.
    if v >= 1:
        return v / 100
    return v


def _normalize_yield(dividend_yield, yield_value) -> float | None:
    """Normalize dividend yield to decimal fraction.

    Yahoo's ``yield`` (key ``"yield"``) and ``dividendYield`` are both returned
    as decimal fractions (e.g. 0.0045 = 0.45%).  No division is needed.  We
    prefer ``yield_value`` (the ``"yield"`` key) and fall back to
    ``dividend_yield`` (the ``"dividendYield"`` key).
    """
    y = _safe_float(yield_value)
    if y is not None:
        return y

    d = _safe_float(dividend_yield)
    return d  # None or already a decimal fraction


def _normalize_return_whole_pct(value) -> float | None:
    """Convert a whole-percent return value to a decimal fraction.

    Use for Yahoo's ``ytdReturn`` field, which is returned as a whole-percent
    number (e.g. 9.09 means +9.09%) and must be divided by 100.
    """
    v = _safe_float(value)
    if v is None:
        return None
    return v / 100


def _normalize_return_decimal(value) -> float | None:
    """Pass through a return value that is already a decimal fraction.

    Use for Yahoo's ``threeYearAverageReturn`` and ``fiveYearAverageReturn``
    fields, which are returned as decimal fractions (e.g. 0.17 = +17%).
    Dividing by 100 would silently destroy legitimate values such as 1.05
    (+105% over 5 years).
    """
    return _safe_float(value)


def _has_profile_fields(info: dict) -> bool:
    """True when info has enough fields to build a profile."""
    if not info:
        return False
    return bool(
        str(info.get("longBusinessSummary") or "").strip()
        or str(info.get("longName") or "").strip()
        or str(info.get("shortName") or "").strip()
        or str(info.get("category") or "").strip()
    )


def _expense_from_fund_operations(ticker: str, funds_data) -> float | None:
    ops = getattr(funds_data, "fund_operations", None)
    if ops is None or getattr(ops, "empty", True):
        return None
    col = ticker.upper()
    if col not in ops.columns or "Annual Report Expense Ratio" not in ops.index:
        return None
    return _safe_float(ops.loc["Annual Report Expense Ratio", col])


def _merge_funds_data(ticker: str, info: dict, funds_data) -> dict:
    """Fill gaps from yfinance FundsData when .info is empty or sparse."""
    merged = dict(info or {})
    if funds_data is None:
        return merged

    description = str(getattr(funds_data, "description", None) or "").strip()
    if description and not merged.get("longBusinessSummary"):
        merged["longBusinessSummary"] = description

    overview = getattr(funds_data, "fund_overview", None) or {}
    if isinstance(overview, dict):
        if overview.get("categoryName") and not merged.get("category"):
            merged["category"] = overview["categoryName"]
        if overview.get("family") and not merged.get("fundFamily"):
            merged["fundFamily"] = overview["family"]
        if overview.get("legalType") and not merged.get("legalType"):
            merged["legalType"] = overview["legalType"]

    if not merged.get("longName") and merged.get("shortName"):
        merged["longName"] = merged["shortName"]

    expense = _expense_from_fund_operations(ticker, funds_data)
    if expense is not None and merged.get("netExpenseRatio") is None:
        merged["netExpenseRatio"] = expense

    return merged


def _fetch_yahoo_info_sync(ticker: str) -> tuple[dict, str]:
    """Single-attempt Yahoo quote fetch (no retry, no sleeping).

    Returns ``(info_dict, error_str)``.  Used by the async retry wrapper below.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {}, "yfinance is not installed (run: pip install -e '.')"

    last_info: dict = {}
    last_error = ""

    try:
        yt = yf.Ticker(ticker)

        # funds_data is more reliable for ETF descriptions when quoteSummary throttles.
        funds_data = None
        try:
            funds_data = yt.funds_data
        except Exception as exc:
            last_error = f"funds_data: {exc}"

        merged = _merge_funds_data(ticker, {}, funds_data)

        try:
            info = yt.get_info() if hasattr(yt, "get_info") else (yt.info or {})
        except Exception as exc:
            info = {}
            last_error = f"get_info: {exc}"

        if not isinstance(info, dict):
            info = {}

        merged = _merge_funds_data(ticker, {**info, **{k: v for k, v in merged.items() if v}}, funds_data)

        if _has_profile_fields(merged):
            return merged, ""
        last_info = merged
        last_error = last_error or "Yahoo returned no fund profile fields"
    except Exception as exc:
        last_error = str(exc)

    return last_info, last_error


async def _fetch_yahoo_info(ticker: str) -> tuple[dict, str]:
    """Fetch Yahoo quote info with async-friendly retries.

    Each attempt runs ``_fetch_yahoo_info_sync`` in a thread via
    ``asyncio.to_thread`` so the event loop is not blocked by network I/O.
    Back-off between attempts uses ``asyncio.sleep`` to free the thread slot
    rather than blocking it with ``time.sleep``.
    """
    ticker = ticker.upper()
    last_info: dict = {}
    last_error = ""

    for attempt in range(_FETCH_RETRIES):
        info, error = await asyncio.to_thread(_fetch_yahoo_info_sync, ticker)
        if not error:
            return info, ""
        last_info = info
        last_error = error
        if attempt < _FETCH_RETRIES - 1:
            await asyncio.sleep(_FETCH_RETRY_DELAY_SEC * (attempt + 1))

    return last_info, last_error


def _parse_yahoo_info(ticker: str, info: dict, fetched_at: str) -> ETFProfile | None:
    if not _has_profile_fields(info):
        return None

    description = str(info.get("longBusinessSummary") or "").strip()
    long_name = str(info.get("longName") or info.get("shortName") or "").strip()
    short_name = str(info.get("shortName") or "").strip()
    category = str(info.get("category") or "").strip()

    expense = _normalize_expense_ratio(info.get("netExpenseRatio"))
    if expense is None:
        expense = _normalize_expense_ratio(info.get("annualReportExpenseRatio"))

    exchange = str(info.get("fullExchangeName") or info.get("exchange") or "").strip()

    return ETFProfile(
        ticker=ticker.upper(),
        long_name=long_name,
        short_name=short_name,
        description=description,
        category=category,
        fund_family=str(info.get("fundFamily") or "").strip(),
        inception_date=_parse_inception_date(info.get("fundInceptionDate")),
        expense_ratio=expense,
        dividend_yield=_normalize_yield(info.get("dividendYield"), info.get("yield")),
        beta=_safe_float(info.get("beta3Year")),
        ytd_return=_normalize_return_whole_pct(info.get("ytdReturn")),
        return_3y=_normalize_return_decimal(info.get("threeYearAverageReturn")),
        return_5y=_normalize_return_decimal(info.get("fiveYearAverageReturn")),
        total_assets=_safe_float(info.get("totalAssets")),
        exchange=exchange,
        avg_volume=_safe_float(info.get("averageVolume")),
        nav_price=_safe_float(info.get("navPrice")),
        legal_type=str(info.get("legalType") or "").strip(),
        num_holdings=_safe_int(info.get("numberOfHoldings")),
        source=SOURCE,
        fetched_at=fetched_at,
    )


def _sanitize_cached_profile(profile: ETFProfile) -> ETFProfile:
    """Fix ytd_return values that were cached as raw whole-percent numbers.

    Yahoo's ``ytdReturn`` field is a whole-percent (e.g. 5.69 = +5.69%).
    Earlier versions of this code cached the raw value without dividing by 100.
    No real ETF has a YTD return greater than ±500%, so any |ytd_return| > 5
    is a clear sign the value was stored un-normalized.
    """
    ytd = profile.ytd_return
    if ytd is not None and abs(ytd) > 5:
        profile = ETFProfile(**{**profile.__dict__, "ytd_return": ytd / 100})
    return profile


def _profile_from_cache(cached: dict) -> ETFProfile | None:
    try:
        data = json.loads(cached["profile_json"])
        profile = ETFProfile(**data)
        return _sanitize_cached_profile(profile)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


async def _fetch_from_yahoo(ticker: str) -> tuple[ETFProfile | None, str]:
    try:
        info, fetch_error = await _fetch_yahoo_info(ticker)
        fetched_at = datetime.now().isoformat()
        profile = _parse_yahoo_info(ticker, info, fetched_at)
        if profile:
            cache_etf_profile(ticker, json.dumps(asdict(profile)), fetched_at)
            return profile, ""
        return None, fetch_error or "Yahoo returned no fund profile fields"
    except ImportError:
        return None, "yfinance is not installed (run: pip install -e '.')"
    except Exception as exc:
        return None, str(exc)


async def get_etf_profile(ticker: str, *, force_refresh: bool = False) -> tuple[ETFProfile | None, str]:
    """Get ETF profile from cache or Yahoo Finance.

    Returns a ``(profile, error)`` tuple.  On success the error string is empty.
    """
    ticker = ticker.upper()

    if not force_refresh:
        cached = get_cached_etf_profile(ticker)
        if cached and cache_is_fresh(cached["fetched_at"], ttl=timedelta(days=PROFILE_CACHE_TTL_DAYS)):
            profile = _profile_from_cache(cached)
            if profile:
                return profile, ""

    return await _fetch_from_yahoo(ticker)


def profile_fetched_date(profile: ETFProfile | None) -> str:
    """Return YYYY-MM-DD date string for profile cache timestamp."""
    if not profile or not profile.fetched_at:
        return ""
    try:
        return datetime.fromisoformat(profile.fetched_at).date().isoformat()
    except (ValueError, TypeError):
        return profile.fetched_at[:10] if len(profile.fetched_at) >= 10 else profile.fetched_at


# ---------------------------------------------------------------------------
# Peer discovery helpers
# ---------------------------------------------------------------------------

# Maps the coarse SEC-derived category (from ETFUniverseEntry) to substrings that
# are likely to appear inside Yahoo Finance's finer-grained category strings.
# The goal is a broad first-pass filter, not a precise match — Yahoo's actual
# category is verified after the profile is fetched.
_COARSE_TO_YAHOO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Sector / Thematic": (
        "sector", "technology", "tech", "health", "biotech", "energy",
        "financial", "communication", "utilities", "consumer", "industrial",
        "materials", "thematic", "innovation", "cyber", "clean", "defense",
        "gaming", "water", "infrastructure", "cannabis", "esports", "cloud",
        "robotics", "semiconductor", "internet",
    ),
    "Fixed Income": (
        "bond", "treasury", "income", "fixed income", "credit", "corporate",
        "municipal", "muni", "inflation", "tips", "yield", "duration",
        "high yield", "floating rate", "preferred",
    ),
    "Broad Market": (
        "equity", "blend", "large cap", "large-cap", "mid cap", "mid-cap",
        "small cap", "small-cap", "total market", "s&p", "russell",
        "growth", "value", "dividend", "market",
    ),
    "Factor / Smart Beta": (
        "factor", "smart beta", "quality", "momentum", "low volatility",
        "minimum volatility", "multi-factor", "dividend", "fundamental",
    ),
    "Real Estate": ("real estate", "reit",),
    "Commodity": (
        "commodity", "commodities", "gold", "silver", "oil", "metal",
        "agriculture", "natural resource",
    ),
    "Multi-Asset": ("multi-asset", "balanced", "allocation", "mixed",),
    "Leveraged / Inverse": ("leveraged", "inverse", "bear", "bull",),
    "Currency": ("currency", "forex",),
}


def _yahoo_category_tokens(yahoo_category: str) -> set[str]:
    """Extract meaningful tokens from a Yahoo category string for fund-name pre-filtering.

    Returns lower-case tokens of length >= 4, excluding generic ETF stop-words.
    e.g. "Health & Biotechnology ETFs" → {"health", "biotechnology"}
    """
    import re

    _STOP = {
        "the", "and", "or", "of", "in", "a", "an", "us", "etf", "etfs",
        "fund", "funds", "index", "with", "for", "cap", "mid", "large",
        "small", "high", "low", "total", "global",
    }
    tokens = re.split(r"[\s,/&\-]+", yahoo_category.lower())
    return {t for t in tokens if len(t) >= 4 and t not in _STOP}


def get_peer_candidates(
    yahoo_category: str,
    universe: list[ETFUniverseEntry],
    cached_tickers: set[str],
    *,
    max_candidates: int = 50,
) -> list[ETFUniverseEntry]:
    """Return universe entries that are plausible peers for *yahoo_category* but not yet cached.

    Uses a two-stage filter:
    1. Coarse category match via keyword heuristic (SEC category → Yahoo keywords).
    2. Fund-name keyword match — requires at least one meaningful token from the
       Yahoo category string to appear in the candidate's fund name.

    Wrong matches are tolerable — callers must verify against Yahoo's actual
    category after fetching the profile.  Results are sorted by fund name for
    deterministic ordering and capped at *max_candidates*.
    """
    ycat = yahoo_category.strip().lower()
    if not ycat:
        return []

    matching_coarse: set[str] = set()
    for coarse, keywords in _COARSE_TO_YAHOO_KEYWORDS.items():
        if any(kw in ycat for kw in keywords):
            matching_coarse.add(coarse)

    if not matching_coarse:
        # No keyword matched — fall back to everything in the universe and let
        # Yahoo confirm category on fetch.
        matching_coarse = set(_COARSE_TO_YAHOO_KEYWORDS.keys())

    # Stage 1: coarse category filter
    stage1 = [
        entry
        for entry in universe
        if entry.category in matching_coarse and entry.ticker not in cached_tickers
    ]

    # Stage 2: fund-name keyword filter — reduces false positives from broad coarse categories
    name_tokens = _yahoo_category_tokens(yahoo_category)
    if name_tokens:
        name_filtered = [
            entry for entry in stage1
            if any(tok in entry.fund_name.lower() for tok in name_tokens)
        ]
        # Fall back to stage1 if the name filter is too aggressive (< 5 results)
        if len(name_filtered) >= 5:
            stage1 = name_filtered

    stage1.sort(key=lambda e: e.fund_name)
    return stage1[:max_candidates]
