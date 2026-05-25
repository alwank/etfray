"""Alternative web holdings scraper service."""

from __future__ import annotations

import io
import json
import re

import httpx
import pandas as pd

from etfray.db.database import cache_holdings, get_cached_holdings

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _fetch_and_parse(ticker: str) -> pd.DataFrame | None:
    """Fetch holdings page and parse embedded data."""
    url = f"https://www.zacks.com/funds/etf/{ticker.upper()}/holding"
    r = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
    if r.status_code != 200:
        return None

    match = re.search(r"etf_holdings\.formatted_data\s*=\s*(\[.*?\])\s*;", r.text, re.DOTALL)
    if not match:
        return None

    raw = re.sub(r",\s*\]", "]", match.group(1))
    data = json.loads(raw)
    if not data:
        return None

    rows = []
    for row in data:
        # [0]=Name HTML, [1]=Ticker HTML, [2]=Shares, [3]=Weight%, [4]=52wk%, [5]=Report
        name_raw = row[0]
        title_m = re.search(r'title="([^"]+)"', name_raw)
        name = title_m.group(1) if title_m else re.sub(r"<[^>]+>", "", name_raw)

        ticker_m = re.search(r'rel="([^"]+)"', row[1])
        symbol = ticker_m.group(1) if ticker_m else ""

        shares_str = row[2].replace(",", "") if row[2] else "0"
        weight_str = row[3].replace(",", "") if row[3] else "0"
        week52_str = row[4].replace(",", "") if row[4] else "0"

        try:
            weight = float(weight_str)
        except ValueError:
            weight = 0.0
        try:
            shares = float(shares_str)
        except ValueError:
            shares = 0.0
        try:
            week52 = float(week52_str) / 100
        except ValueError:
            week52 = 0.0

        rows.append(
            {
                "ticker": symbol,
                "name": name,
                "pct_value": weight,
                "balance": shares,
                "week52_return": week52,
            }
        )

    return pd.DataFrame(rows)


def get_holdings_from_web(ticker: str) -> pd.DataFrame | None:
    """Get holdings from web source, using cache if available."""
    ticker = ticker.upper()

    # Check cache
    cached = get_cached_holdings(ticker, source="web")
    if cached and cached.get("holdings_json"):
        try:
            df_cached = pd.read_json(io.StringIO(cached["holdings_json"]))
            # Stale cache entries (written before the /100 normalisation was introduced)
            # store week52_return as raw percent numbers (e.g. 63.99) rather than decimals
            # (e.g. 0.6399).  Detect this by checking whether the median absolute value of
            # the non-zero returns is > 1, which is impossible for a decimal representation
            # of a reasonable annual return.  When detected, re-fetch and overwrite the cache.
            if "week52_return" in df_cached.columns:
                nonzero = df_cached["week52_return"][df_cached["week52_return"] != 0]
                if not nonzero.empty and nonzero.abs().median() > 1.0:
                    df_cached = None  # fall through to fresh fetch
            if df_cached is not None:
                return df_cached
        except Exception:
            pass

    # Fetch fresh
    df = _fetch_and_parse(ticker)
    if df is None or df.empty:
        return None

    from datetime import date

    cache_holdings(ticker, df.to_json(), date.today().isoformat(), "", source="web")
    return df
