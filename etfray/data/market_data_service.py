"""Market data service — Yahoo Finance profile metadata via yfinance."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from etfray.db.database import cache_etf_profile, get_cached_etf_profile

PROFILE_CACHE_TTL_DAYS = 7
SOURCE = "yahoo"
_FETCH_RETRIES = 3
_FETCH_RETRY_DELAY_SEC = 0.75

_last_profile_error: str = ""


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
    source: str = SOURCE
    fetched_at: str = ""


def get_profile_last_error() -> str:
    """Human-readable reason the most recent profile fetch failed."""
    return _last_profile_error


def _set_profile_error(message: str) -> None:
    global _last_profile_error
    _last_profile_error = message


def _clear_profile_error() -> None:
    global _last_profile_error
    _last_profile_error = ""


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
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
    # Yahoo returns either 0.0003 (decimal) or 0.06 (meaning 0.06%).
    if v >= 0.005:
        return v / 100
    return v


def _normalize_yield(dividend_yield, yield_value) -> float | None:
    """Normalize dividend yield to decimal fraction."""
    y = _safe_float(yield_value)
    if y is not None:
        return y / 100 if y >= 0.5 else y

    d = _safe_float(dividend_yield)
    if d is None:
        return None
    return d / 100 if d >= 0.5 else d


def _normalize_return(value) -> float | None:
    """Normalize return fields to decimal fraction."""
    v = _safe_float(value)
    if v is None:
        return None
    # ytdReturn is often whole-percent (9.09); multi-year returns are often decimal (0.17).
    if abs(v) > 1:
        return v / 100
    return v


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


def _fetch_yahoo_info(ticker: str) -> dict:
    """Fetch Yahoo quote info with retries and funds_data fallback."""
    try:
        import yfinance as yf
    except ImportError:
        _set_profile_error("yfinance is not installed (run: pip install -e '.')")
        return {}

    ticker = ticker.upper()
    last_info: dict = {}
    last_error = ""

    for attempt in range(_FETCH_RETRIES):
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
                return merged
            last_info = merged
            last_error = last_error or "Yahoo returned no fund profile fields"
        except Exception as exc:
            last_error = str(exc)
        if attempt < _FETCH_RETRIES - 1:
            time.sleep(_FETCH_RETRY_DELAY_SEC * (attempt + 1))

    if last_error:
        _set_profile_error(last_error)
    return last_info


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
        ytd_return=_normalize_return(info.get("ytdReturn")),
        return_3y=_normalize_return(info.get("threeYearAverageReturn")),
        return_5y=_normalize_return(info.get("fiveYearAverageReturn")),
        total_assets=_safe_float(info.get("totalAssets")),
        exchange=exchange,
        avg_volume=_safe_float(info.get("averageVolume")),
        nav_price=_safe_float(info.get("navPrice")),
        legal_type=str(info.get("legalType") or "").strip(),
        source=SOURCE,
        fetched_at=fetched_at,
    )


def _profile_from_cache(cached: dict) -> ETFProfile | None:
    try:
        data = json.loads(cached["profile_json"])
        return ETFProfile(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def _cache_is_fresh(fetched_at: str, *, now: datetime | None = None) -> bool:
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except (ValueError, TypeError):
        return False
    current = now or datetime.now()
    return current - fetched < timedelta(days=PROFILE_CACHE_TTL_DAYS)


def _fetch_from_yahoo(ticker: str) -> ETFProfile | None:
    try:
        info = _fetch_yahoo_info(ticker)
        fetched_at = datetime.now().isoformat()
        profile = _parse_yahoo_info(ticker, info, fetched_at)
        if profile:
            _clear_profile_error()
            cache_etf_profile(ticker, json.dumps(asdict(profile)), fetched_at)
            return profile
        if not _last_profile_error:
            _set_profile_error("Yahoo returned no fund profile fields")
        return None
    except ImportError:
        _set_profile_error("yfinance is not installed (run: pip install -e '.')")
        return None
    except Exception as exc:
        _set_profile_error(str(exc))
        return None


def get_etf_profile(ticker: str, *, force_refresh: bool = False) -> ETFProfile | None:
    """Get ETF profile from cache or Yahoo Finance."""
    ticker = ticker.upper()

    if not force_refresh:
        cached = get_cached_etf_profile(ticker)
        if cached and _cache_is_fresh(cached["fetched_at"]):
            profile = _profile_from_cache(cached)
            if profile:
                _clear_profile_error()
                return profile

    return _fetch_from_yahoo(ticker)


def profile_fetched_date(profile: ETFProfile | None) -> str:
    """Return YYYY-MM-DD date string for profile cache timestamp."""
    if not profile or not profile.fetched_at:
        return ""
    try:
        return datetime.fromisoformat(profile.fetched_at).date().isoformat()
    except (ValueError, TypeError):
        return profile.fetched_at[:10] if len(profile.fetched_at) >= 10 else profile.fetched_at
