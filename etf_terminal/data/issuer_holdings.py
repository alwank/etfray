"""ETF issuer daily holdings downloader (iShares, SSGA, Vanguard)."""

from __future__ import annotations

import io
import time
from datetime import date

import pandas as pd
import httpx

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ETFTerminal/1.0"

# iShares: ticker -> (product_id, slug)
ISHARES_MAP: dict[str, tuple[str, str]] = {
    "IVV": ("239726", "ishares-core-sp-500-etf"),
    "AGG": ("239458", "ishares-core-us-aggregate-bond-etf"),
    "IWM": ("239710", "ishares-russell-2000-etf"),
    "EFA": ("239623", "ishares-msci-eafe-etf"),
    "EEM": ("239637", "ishares-msci-emerging-markets-etf"),
    "IWF": ("239706", "ishares-russell-1000-growth-etf"),
    "IWD": ("239708", "ishares-russell-1000-value-etf"),
    "IJH": ("239763", "ishares-core-sp-mid-cap-etf"),
    "IJR": ("239774", "ishares-core-sp-small-cap-etf"),
    "IEMG": ("244050", "ishares-core-msci-emerging-markets-etf"),
    "LQD": ("239566", "ishares-iboxx-investment-grade-corporate-bond-etf"),
    "HYG": ("239565", "ishares-iboxx-high-yield-corporate-bond-etf"),
    "TIP": ("239467", "ishares-tips-bond-etf"),
    "SHY": ("239452", "ishares-1-3-year-treasury-bond-etf"),
    "IEF": ("239456", "ishares-7-10-year-treasury-bond-etf"),
    "TLT": ("239454", "ishares-20-plus-year-treasury-bond-etf"),
    "GOVT": ("239468", "ishares-us-treasury-bond-etf"),
    "MUB": ("239766", "ishares-national-muni-bond-etf"),
    "EMB": ("239572", "ishares-jp-morgan-usd-emerging-markets-bond-etf"),
    "IGSB": ("239451", "ishares-1-5-year-investment-grade-corporate-bond-etf"),
    "ITOT": ("239724", "ishares-core-sp-total-us-stock-market-etf"),
    "IEFA": ("244049", "ishares-core-msci-eafe-etf"),
    "IWB": ("239707", "ishares-russell-1000-etf"),
}

# SSGA/SPDR: ticker -> lowercase ticker for URL
SSGA_MAP: set[str] = {
    "SPY", "GLD", "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    "MDY", "DIA", "SDY", "SPYG", "SPYV", "SPDW", "SPEM",
}

# Vanguard: ticker -> portId
VANGUARD_MAP: dict[str, str] = {
    "VTI": "0970",
    "VXUS": "3369",
    "VEA": "0936",
    "VWO": "0964",
    "BND": "0928",
    "BNDX": "3711",
    "VOO": "0968",
    "VIG": "0920",
    "VYM": "0923",
    "VGT": "0958",
    "VNQ": "0986",
    "VGIT": "3143",
    "VTIP": "3533",
    "VTV": "0966",
    "VUG": "0967",
    "VO": "0955",
    "VB": "0951",
    "VGSH": "3144",
    "VCIT": ("3140"),
    "VCSH": "3141",
}


def download_ishares_holdings(ticker: str) -> pd.DataFrame | None:
    """Download daily holdings CSV from iShares."""
    ticker = ticker.upper()
    if ticker not in ISHARES_MAP:
        return None

    product_id, slug = ISHARES_MAP[ticker]
    url = (
        f"https://www.ishares.com/us/products/{product_id}/{slug}/"
        f"1467271812596.ajax?fileType=csv&fileName={ticker}_holdings&dataType=fund"
    )

    try:
        time.sleep(1)
        resp = httpx.get(url, headers={"User-Agent": _UA}, timeout=30, follow_redirects=True)
        if resp.status_code != 200:
            return None

        # iShares CSV has metadata rows at top, find the header row
        lines = resp.text.splitlines()
        header_idx = None
        for i, line in enumerate(lines):
            if "Ticker" in line and "Name" in line and "Weight" in line:
                header_idx = i
                break

        if header_idx is None:
            # Try alternate: look for "Issuer" header pattern
            for i, line in enumerate(lines):
                if "Ticker" in line and "Sector" in line:
                    header_idx = i
                    break

        if header_idx is None:
            return None

        csv_text = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_text))

        # Normalize columns
        col_map = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl == "ticker":
                col_map[c] = "ticker"
            elif cl == "name":
                col_map[c] = "name"
            elif cl in ("weight", "weight (%)"):
                col_map[c] = "pct_value"
            elif cl in ("market value", "market_value"):
                col_map[c] = "value_usd"
            elif cl == "shares":
                col_map[c] = "balance"
            elif cl == "sector":
                col_map[c] = "sector"
            elif cl in ("location", "country"):
                col_map[c] = "investment_country"
            elif cl in ("asset class", "asset_class"):
                col_map[c] = "asset_category"

        df = df.rename(columns=col_map)

        # Clean numeric columns
        for col in ["pct_value", "value_usd", "balance"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.replace("-", ""), errors="coerce")

        # Drop rows with no ticker/name
        if "name" in df.columns:
            df = df.dropna(subset=["name"])
            df = df[df["name"].str.strip() != ""]

        return df if not df.empty else None
    except Exception:
        return None


def download_ssga_holdings(ticker: str) -> pd.DataFrame | None:
    """Download daily holdings from SSGA/SPDR."""
    ticker = ticker.upper()
    if ticker not in SSGA_MAP:
        return None

    url = f"https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{ticker.lower()}.xlsx"

    try:
        time.sleep(1)
        resp = httpx.get(url, headers={"User-Agent": _UA}, timeout=30, follow_redirects=True)
        if resp.status_code != 200:
            return None

        df = pd.read_excel(io.BytesIO(resp.content), engine="openpyxl", skiprows=4)

        # Normalize columns
        col_map = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl in ("ticker", "symbol"):
                col_map[c] = "ticker"
            elif cl == "name":
                col_map[c] = "name"
            elif cl in ("weight", "weight (%)"):
                col_map[c] = "pct_value"
            elif cl in ("market value",):
                col_map[c] = "value_usd"
            elif cl in ("shares held", "shares"):
                col_map[c] = "balance"
            elif cl == "sector":
                col_map[c] = "sector"

        df = df.rename(columns=col_map)

        for col in ["pct_value", "value_usd", "balance"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "name" in df.columns:
            df = df.dropna(subset=["name"])

        return df if not df.empty else None
    except Exception:
        return None


def download_vanguard_holdings(ticker: str) -> pd.DataFrame | None:
    """Download daily holdings from Vanguard."""
    ticker = ticker.upper()
    if ticker not in VANGUARD_MAP:
        return None

    port_id = VANGUARD_MAP[ticker]
    url = f"https://advisors.vanguard.com/web/c1/fas-investmentproducts/{port_id}/portfolio/holding/stock.csv"

    try:
        time.sleep(1)
        resp = httpx.get(url, headers={"User-Agent": _UA}, timeout=30, follow_redirects=True)
        if resp.status_code != 200:
            return None

        df = pd.read_csv(io.StringIO(resp.text))

        # Normalize columns
        col_map = {}
        for c in df.columns:
            cl = c.strip().lower()
            if cl in ("ticker", "symbol", "ticker symbol"):
                col_map[c] = "ticker"
            elif cl in ("holding name", "name", "short name"):
                col_map[c] = "name"
            elif cl in ("% of fund", "percentage", "weight"):
                col_map[c] = "pct_value"
            elif cl in ("market value", "market_value"):
                col_map[c] = "value_usd"
            elif cl in ("shares", "quantity"):
                col_map[c] = "balance"
            elif cl == "sector":
                col_map[c] = "sector"
            elif cl == "country":
                col_map[c] = "investment_country"

        df = df.rename(columns=col_map)

        for col in ["pct_value", "value_usd", "balance"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.replace("%", ""), errors="coerce")

        if "name" in df.columns:
            df = df.dropna(subset=["name"])

        return df if not df.empty else None
    except Exception:
        return None


def get_issuer_holdings(ticker: str) -> pd.DataFrame | None:
    """Try all issuer sources for a ticker. Returns DataFrame or None."""
    ticker = ticker.upper()

    if ticker in ISHARES_MAP:
        return download_ishares_holdings(ticker)
    if ticker in SSGA_MAP:
        return download_ssga_holdings(ticker)
    if ticker in VANGUARD_MAP:
        return download_vanguard_holdings(ticker)

    return None


def is_issuer_supported(ticker: str) -> bool:
    """Check if a ticker has issuer daily holdings support."""
    t = ticker.upper()
    return t in ISHARES_MAP or t in SSGA_MAP or t in VANGUARD_MAP
