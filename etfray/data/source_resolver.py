"""Source resolver - picks the best holdings source based on user preference."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from etfray.db.database import get_cached_holdings


def _parse_date(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.fromisoformat(d).date()
    except (ValueError, TypeError):
        return None


def resolve_holdings(ticker: str, preference: str = "auto") -> tuple[pd.DataFrame | None, str]:
    """Return (df, source_name) based on preference.

    preference: "auto" | "edgar" | "web"
    Returns the holdings DataFrame and which source was used.
    """
    ticker = ticker.upper()

    if preference == "edgar":
        from etfray.data.edgar_service import get_holdings_df
        df = get_holdings_df(ticker)
        return df, "edgar"

    if preference == "web":
        from etfray.data.web_service import get_holdings_from_web
        df = get_holdings_from_web(ticker)
        return df, "web"

    # Auto: prefer freshest
    edgar_date = _parse_date((get_cached_holdings(ticker, source="nport") or {}).get("as_of_date"))
    web_date = _parse_date((get_cached_holdings(ticker, source="web") or {}).get("as_of_date"))

    # If both cached, pick fresher
    if edgar_date and web_date:
        if web_date >= edgar_date:
            from etfray.data.web_service import get_holdings_from_web
            df = get_holdings_from_web(ticker)
            if df is not None and not df.empty:
                return df, "web"
        from etfray.data.edgar_service import get_holdings_df
        df = get_holdings_df(ticker)
        return df, "edgar"

    # If only one cached, use it; fetch the other
    if edgar_date and not web_date:
        from etfray.data.web_service import get_holdings_from_web
        wdf = get_holdings_from_web(ticker)
        if wdf is not None and not wdf.empty:
            web_date = _parse_date((get_cached_holdings(ticker, source="web") or {}).get("as_of_date"))
            if web_date and web_date > edgar_date:
                return wdf, "web"
        from etfray.data.edgar_service import get_holdings_df
        return get_holdings_df(ticker), "edgar"

    if web_date and not edgar_date:
        from etfray.data.edgar_service import get_holdings_df
        edf = get_holdings_df(ticker)
        if edf is not None and not edf.empty:
            edgar_date = _parse_date((get_cached_holdings(ticker, source="nport") or {}).get("as_of_date"))
            if edgar_date and edgar_date > web_date:
                return edf, "edgar"
        from etfray.data.web_service import get_holdings_from_web
        return get_holdings_from_web(ticker), "web"

    # Neither cached — try edgar first, then web
    from etfray.data.edgar_service import get_holdings_df
    edf = get_holdings_df(ticker)
    if edf is not None and not edf.empty:
        return edf, "edgar"
    from etfray.data.web_service import get_holdings_from_web
    wdf = get_holdings_from_web(ticker)
    if wdf is not None and not wdf.empty:
        return wdf, "web"
    return None, "none"


def get_freshness_comparison(ticker: str) -> str | None:
    """Return a badge string if web source has newer data than EDGAR, else None."""
    ticker = ticker.upper()
    edgar_date = _parse_date((get_cached_holdings(ticker, source="nport") or {}).get("as_of_date"))
    web_date = _parse_date((get_cached_holdings(ticker, source="web") or {}).get("as_of_date"))

    if web_date and edgar_date and web_date > edgar_date:
        return f"⚡ Web source has newer weights ({web_date.isoformat()})"
    return None
