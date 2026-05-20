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

    preference: "auto" | "edgar" | "zacks"
    Returns the holdings DataFrame and which source was used.
    """
    ticker = ticker.upper()

    if preference == "edgar":
        from etfray.data.edgar_service import get_holdings_df
        df = get_holdings_df(ticker)
        return df, "edgar"

    if preference == "zacks":
        from etfray.data.zacks_service import get_holdings_from_zacks
        df = get_holdings_from_zacks(ticker)
        return df, "zacks"

    # Auto: prefer freshest
    edgar_date = _parse_date((get_cached_holdings(ticker, source="nport") or {}).get("as_of_date"))
    zacks_date = _parse_date((get_cached_holdings(ticker, source="zacks") or {}).get("as_of_date"))

    # If both cached, pick fresher
    if edgar_date and zacks_date:
        if zacks_date >= edgar_date:
            from etfray.data.zacks_service import get_holdings_from_zacks
            df = get_holdings_from_zacks(ticker)
            if df is not None and not df.empty:
                return df, "zacks"
        from etfray.data.edgar_service import get_holdings_df
        df = get_holdings_df(ticker)
        return df, "edgar"

    # If only one cached, use it; fetch the other
    if edgar_date and not zacks_date:
        from etfray.data.zacks_service import get_holdings_from_zacks
        zdf = get_holdings_from_zacks(ticker)
        if zdf is not None and not zdf.empty:
            zacks_date = _parse_date((get_cached_holdings(ticker, source="zacks") or {}).get("as_of_date"))
            if zacks_date and zacks_date > edgar_date:
                return zdf, "zacks"
        from etfray.data.edgar_service import get_holdings_df
        return get_holdings_df(ticker), "edgar"

    if zacks_date and not edgar_date:
        from etfray.data.edgar_service import get_holdings_df
        edf = get_holdings_df(ticker)
        if edf is not None and not edf.empty:
            edgar_date = _parse_date((get_cached_holdings(ticker, source="nport") or {}).get("as_of_date"))
            if edgar_date and edgar_date > zacks_date:
                return edf, "edgar"
        from etfray.data.zacks_service import get_holdings_from_zacks
        return get_holdings_from_zacks(ticker), "zacks"

    # Neither cached — try edgar first, then zacks
    from etfray.data.edgar_service import get_holdings_df
    edf = get_holdings_df(ticker)
    if edf is not None and not edf.empty:
        return edf, "edgar"
    from etfray.data.zacks_service import get_holdings_from_zacks
    zdf = get_holdings_from_zacks(ticker)
    if zdf is not None and not zdf.empty:
        return zdf, "zacks"
    return None, "none"


def get_freshness_comparison(ticker: str) -> str | None:
    """Return a badge string if Zacks has newer data than EDGAR, else None."""
    ticker = ticker.upper()
    edgar_date = _parse_date((get_cached_holdings(ticker, source="nport") or {}).get("as_of_date"))
    zacks_date = _parse_date((get_cached_holdings(ticker, source="zacks") or {}).get("as_of_date"))

    if zacks_date and edgar_date and zacks_date > edgar_date:
        return f"⚡ Zacks has newer weights ({zacks_date.isoformat()})"
    return None
