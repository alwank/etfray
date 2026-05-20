"""Sector lookup service - static GICS mapping + Zacks fallback."""

from __future__ import annotations

import re
import httpx

# Static S&P 500 GICS sector mapping (as of May 2026)
SECTOR_MAP: dict[str, str] = {
    "MMM": "Industrials", "AOS": "Industrials", "ABT": "Health Care", "ABBV": "Health Care",
    "ACN": "Information Technology", "ADBE": "Information Technology", "AMD": "Information Technology",
    "AES": "Utilities", "AFL": "Financials", "A": "Health Care", "APD": "Materials",
    "ABNB": "Consumer Discretionary", "AKAM": "Information Technology", "ALB": "Materials",
    "ARE": "Real Estate", "ALGN": "Health Care", "ALLE": "Industrials", "LNT": "Utilities",
    "ALL": "Financials", "GOOGL": "Communication Services", "GOOG": "Communication Services",
    "MO": "Consumer Staples", "AMZN": "Consumer Discretionary", "AMCR": "Materials",
    "AEE": "Utilities", "AEP": "Utilities", "AXP": "Financials", "AIG": "Financials",
    "AMT": "Real Estate", "AWK": "Utilities", "AMP": "Financials", "AME": "Industrials",
    "AMGN": "Health Care", "APH": "Information Technology", "ADI": "Information Technology",
    "AON": "Financials", "APA": "Energy", "APO": "Financials", "AAPL": "Information Technology",
    "AMAT": "Information Technology", "APP": "Information Technology", "APTV": "Consumer Discretionary",
    "ACGL": "Financials", "ADM": "Consumer Staples", "ARES": "Financials",
    "ANET": "Information Technology", "AJG": "Financials", "AIZ": "Financials",
    "T": "Communication Services", "ATO": "Utilities", "ADSK": "Information Technology",
    "ADP": "Industrials", "AZO": "Consumer Discretionary", "AVB": "Real Estate",
    "AVY": "Materials", "AXON": "Industrials", "BKR": "Energy", "BALL": "Materials",
    "BAC": "Financials", "BAX": "Health Care", "BDX": "Health Care", "BRK.B": "Financials",
    "BBY": "Consumer Discretionary", "TECH": "Health Care", "BIIB": "Health Care",
    "BLK": "Financials", "BX": "Financials", "XYZ": "Financials", "BK": "Financials",
    "BA": "Industrials", "BKNG": "Consumer Discretionary", "BSX": "Health Care",
    "BMY": "Health Care", "AVGO": "Information Technology", "BR": "Industrials",
    "BRO": "Financials", "BF.B": "Consumer Staples", "BLDR": "Industrials",
    "BG": "Consumer Staples", "BXP": "Real Estate", "CHRW": "Industrials",
    "CDNS": "Information Technology", "CPT": "Real Estate", "CPB": "Consumer Staples",
    "COF": "Financials", "CAH": "Health Care", "CCL": "Consumer Discretionary",
    "CARR": "Industrials", "CVNA": "Consumer Discretionary", "CASY": "Consumer Staples",
    "CAT": "Industrials", "CBOE": "Financials", "CBRE": "Real Estate",
    "CDW": "Information Technology", "COR": "Health Care", "CNC": "Health Care",
    "CNP": "Utilities", "CF": "Materials", "CRL": "Health Care", "SCHW": "Financials",
    "CHTR": "Communication Services", "CVX": "Energy", "CMG": "Consumer Discretionary",
    "CB": "Financials", "CHD": "Consumer Staples", "CIEN": "Information Technology",
    "CI": "Health Care", "CINF": "Financials", "CTAS": "Industrials",
    "CSCO": "Information Technology", "C": "Financials", "CFG": "Financials",
    "CLX": "Consumer Staples", "CME": "Financials", "CMS": "Utilities",
    "KO": "Consumer Staples", "CTSH": "Information Technology", "COHR": "Information Technology",
    "COIN": "Financials", "CL": "Consumer Staples", "CMCSA": "Communication Services",
    "FIX": "Industrials", "CAG": "Consumer Staples", "COP": "Energy", "ED": "Utilities",
    "STZ": "Consumer Staples", "CEG": "Utilities", "COO": "Health Care",
    "CPRT": "Industrials", "GLW": "Information Technology", "CPAY": "Financials",
    "CTVA": "Materials", "CSGP": "Real Estate", "COST": "Consumer Staples",
    "CTRA": "Energy", "CCI": "Real Estate", "CSX": "Industrials", "CMI": "Industrials",
    "CVS": "Health Care", "DHI": "Consumer Discretionary", "DHR": "Health Care",
    "DRI": "Consumer Discretionary", "DVA": "Health Care", "DAY": "Information Technology",
    "DECK": "Consumer Discretionary", "DE": "Industrials", "DAL": "Industrials",
    "DVN": "Energy", "DXCM": "Health Care", "FANG": "Energy", "DLR": "Real Estate",
    "DFS": "Financials", "DG": "Consumer Staples", "DLTR": "Consumer Discretionary",
    "D": "Utilities", "DPZ": "Consumer Discretionary", "DOV": "Industrials",
    "DOW": "Materials", "DD": "Materials", "DTE": "Utilities", "DUK": "Utilities",
    "DXC": "Information Technology", "EMN": "Materials", "ETN": "Industrials",
    "EBAY": "Consumer Discretionary", "ECL": "Materials", "EIX": "Utilities",
    "EW": "Health Care", "EA": "Communication Services", "ELV": "Health Care",
    "EMR": "Industrials", "ENPH": "Information Technology", "ETR": "Utilities",
    "EOG": "Energy", "EPAM": "Information Technology", "EQT": "Energy",
    "EFX": "Industrials", "EQIX": "Real Estate", "EQR": "Real Estate",
    "ERIE": "Financials", "ESS": "Real Estate", "EL": "Consumer Staples",
    "EG": "Financials", "EVRG": "Utilities", "ES": "Utilities", "EXC": "Utilities",
    "EXPE": "Consumer Discretionary", "EXPD": "Industrials", "EXR": "Real Estate",
    "XOM": "Energy", "FFIV": "Information Technology", "FDS": "Financials",
    "FICO": "Information Technology", "FAST": "Industrials", "FRT": "Real Estate",
    "FDX": "Industrials", "FIS": "Financials", "FITB": "Financials",
    "FSLR": "Information Technology", "FE": "Utilities", "FI": "Financials",
    "FMC": "Materials", "F": "Consumer Discretionary", "FTNT": "Information Technology",
    "FTV": "Industrials", "FOXA": "Communication Services", "FOX": "Communication Services",
    "BEN": "Financials", "FCX": "Materials", "GRMN": "Consumer Discretionary",
    "IT": "Information Technology", "GE": "Industrials", "GEHC": "Health Care",
    "GEV": "Industrials", "GEN": "Information Technology", "GNRC": "Industrials",
    "GD": "Industrials", "GIS": "Consumer Staples", "GM": "Consumer Discretionary",
    "GPC": "Consumer Discretionary", "GILD": "Health Care", "GPN": "Financials",
    "GL": "Financials", "GS": "Financials", "HAL": "Energy", "HIG": "Financials",
    "HAS": "Consumer Discretionary", "HCA": "Health Care", "DOC": "Real Estate",
    "HSIC": "Health Care", "HSY": "Consumer Staples", "HES": "Energy",
    "HPE": "Information Technology", "HLT": "Consumer Discretionary", "HOLX": "Health Care",
    "HD": "Consumer Discretionary", "HON": "Industrials", "HRL": "Consumer Staples",
    "HST": "Real Estate", "HWM": "Industrials", "HPQ": "Information Technology",
    "HUBB": "Industrials", "HUM": "Health Care", "HBAN": "Financials",
    "HII": "Industrials", "IBM": "Information Technology", "IEX": "Industrials",
    "IDXX": "Health Care", "ITW": "Industrials", "ILMN": "Health Care",
    "INCY": "Health Care", "IR": "Industrials", "PODD": "Health Care",
    "INTC": "Information Technology", "ICE": "Financials", "IFF": "Materials",
    "IP": "Materials", "IPG": "Communication Services", "INTU": "Information Technology",
    "ISRG": "Health Care", "IVZ": "Financials", "INVH": "Real Estate",
    "IQV": "Health Care", "IRM": "Real Estate", "JBHT": "Industrials",
    "JBL": "Information Technology", "JKHY": "Information Technology", "J": "Industrials",
    "JNJ": "Health Care", "JCI": "Industrials", "JPM": "Financials",
    "JNPR": "Information Technology", "K": "Consumer Staples", "KVUE": "Consumer Staples",
    "KDP": "Consumer Staples", "KEY": "Financials", "KEYS": "Information Technology",
    "KMB": "Consumer Staples", "KIM": "Real Estate", "KMI": "Energy",
    "KKR": "Financials", "KLAC": "Information Technology", "KHC": "Consumer Staples",
    "KR": "Consumer Staples", "LHX": "Industrials", "LH": "Health Care",
    "LRCX": "Information Technology", "LW": "Consumer Staples", "LVS": "Consumer Discretionary",
    "LDOS": "Information Technology", "LEN": "Consumer Discretionary", "LLY": "Health Care",
    "LIN": "Materials", "LYV": "Communication Services", "LKQ": "Consumer Discretionary",
    "LMT": "Industrials", "L": "Financials", "LOW": "Consumer Discretionary",
    "LULU": "Consumer Discretionary", "LYB": "Materials", "MTB": "Financials",
    "MRO": "Energy", "MPC": "Energy", "MKTX": "Financials", "MAR": "Consumer Discretionary",
    "MMC": "Financials", "MLM": "Materials", "MAS": "Industrials", "MA": "Financials",
    "MTCH": "Communication Services", "MKC": "Consumer Staples", "MCD": "Consumer Discretionary",
    "MCK": "Health Care", "MDT": "Health Care", "MRK": "Health Care",
    "META": "Communication Services", "MET": "Financials", "MTD": "Health Care",
    "MGM": "Consumer Discretionary", "MCHP": "Information Technology", "MU": "Information Technology",
    "MSFT": "Information Technology", "MAA": "Real Estate", "MRNA": "Health Care",
    "MHK": "Consumer Discretionary", "MOH": "Health Care", "TAP": "Consumer Staples",
    "MDLZ": "Consumer Staples", "MPWR": "Information Technology", "MNST": "Consumer Staples",
    "MCO": "Financials", "MS": "Financials", "MOS": "Materials",
    "MSI": "Information Technology", "MSCI": "Financials", "NDAQ": "Financials",
    "NTAP": "Information Technology", "NFLX": "Communication Services", "NEM": "Materials",
    "NWSA": "Communication Services", "NWS": "Communication Services", "NEE": "Utilities",
    "NKE": "Consumer Discretionary", "NI": "Utilities", "NDSN": "Industrials",
    "NSC": "Industrials", "NTRS": "Financials", "NOC": "Industrials",
    "NCLH": "Consumer Discretionary", "NRG": "Utilities", "NUE": "Materials",
    "NVDA": "Information Technology", "NVR": "Consumer Discretionary", "NXPI": "Information Technology",
    "ORLY": "Consumer Discretionary", "OXY": "Energy", "ODFL": "Industrials",
    "OMC": "Communication Services", "ON": "Information Technology", "OKE": "Energy",
    "ORCL": "Information Technology", "OTIS": "Industrials", "PCAR": "Industrials",
    "PKG": "Materials", "PANW": "Information Technology", "PARA": "Communication Services",
    "PH": "Industrials", "PAYX": "Industrials", "PAYC": "Information Technology",
    "PYPL": "Financials", "PNR": "Industrials", "PEP": "Consumer Staples",
    "PFE": "Health Care", "PCG": "Utilities", "PM": "Consumer Staples",
    "PSX": "Energy", "PNW": "Utilities", "PXD": "Energy", "PNC": "Financials",
    "POOL": "Consumer Discretionary", "PPG": "Materials", "PPL": "Utilities",
    "PFG": "Financials", "PG": "Consumer Staples", "PGR": "Financials",
    "PLD": "Real Estate", "PRU": "Financials", "PEG": "Utilities",
    "PTC": "Information Technology", "PSA": "Real Estate", "PHM": "Consumer Discretionary",
    "QRVO": "Information Technology", "PWR": "Industrials", "QCOM": "Information Technology",
    "DGX": "Health Care", "RL": "Consumer Discretionary", "RJF": "Financials",
    "RTX": "Industrials", "O": "Real Estate", "REG": "Real Estate",
    "REGN": "Health Care", "RF": "Financials", "RSG": "Industrials",
    "RMD": "Health Care", "RVTY": "Health Care", "RHI": "Industrials",
    "ROK": "Industrials", "ROL": "Industrials", "ROP": "Information Technology",
    "ROST": "Consumer Discretionary", "RCL": "Consumer Discretionary", "SPGI": "Financials",
    "CRM": "Information Technology", "SBAC": "Real Estate", "SLB": "Energy",
    "STX": "Information Technology", "SRE": "Utilities", "NOW": "Information Technology",
    "SHW": "Materials", "SPG": "Real Estate", "SWKS": "Information Technology",
    "SJM": "Consumer Staples", "SW": "Health Care", "SNA": "Industrials",
    "SOLV": "Health Care", "SO": "Utilities", "LUV": "Industrials",
    "SWK": "Industrials", "SBUX": "Consumer Discretionary", "STT": "Financials",
    "STLD": "Materials", "STE": "Health Care", "SYK": "Health Care",
    "SMCI": "Information Technology", "SYF": "Financials", "SNPS": "Information Technology",
    "SYY": "Consumer Staples", "TMUS": "Communication Services", "TROW": "Financials",
    "TTWO": "Communication Services", "TPR": "Consumer Discretionary", "TRGP": "Energy",
    "TGT": "Consumer Staples", "TEL": "Information Technology", "TDY": "Industrials",
    "TFX": "Health Care", "TER": "Information Technology", "TSLA": "Consumer Discretionary",
    "TXN": "Information Technology", "TXT": "Industrials", "TMO": "Health Care",
    "TJX": "Consumer Discretionary", "TSCO": "Consumer Discretionary", "TT": "Industrials",
    "TDG": "Industrials", "TRV": "Financials", "TRMB": "Information Technology",
    "TFC": "Financials", "TYL": "Information Technology", "TSN": "Consumer Staples",
    "USB": "Financials", "UBER": "Industrials", "UDR": "Real Estate",
    "ULTA": "Consumer Discretionary", "UNP": "Industrials", "UAL": "Industrials",
    "UPS": "Industrials", "URI": "Industrials", "UNH": "Health Care",
    "UHS": "Health Care", "VLO": "Energy", "VTR": "Real Estate",
    "VLTO": "Industrials", "VRSN": "Information Technology", "VRSK": "Industrials",
    "VZ": "Communication Services", "VRTX": "Health Care", "VEEV": "Health Care",
    "VFC": "Consumer Discretionary", "V": "Financials", "VMC": "Materials",
    "WRB": "Financials", "GWW": "Industrials", "WAB": "Industrials",
    "WMT": "Consumer Staples", "DIS": "Communication Services", "WBD": "Communication Services",
    "WM": "Industrials", "WAT": "Health Care", "WEC": "Utilities",
    "WFC": "Financials", "WELL": "Real Estate", "WST": "Health Care",
    "WDC": "Information Technology", "WY": "Real Estate", "WSM": "Consumer Discretionary",
    "WMB": "Energy", "WTW": "Financials", "WDAY": "Information Technology",
    "WYNN": "Consumer Discretionary", "XEL": "Utilities", "XYL": "Industrials",
    "YUM": "Consumer Discretionary", "ZBRA": "Information Technology", "ZBH": "Health Care",
    "ZTS": "Health Care", "SATS": "Communication Services", "LITE": "Information Technology",
    "VRT": "Industrials",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def _scrape_sector_zacks(ticker: str) -> str | None:
    """Scrape sector from Zacks stock quote page."""
    try:
        url = f"https://www.zacks.com/stock/quote/{ticker.upper()}"
        r = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            return None
        # Look for sector in the page
        m = re.search(r'Sector</a>\s*</td>\s*<td[^>]*>\s*<a[^>]*>([^<]+)</a>', r.text)
        if m:
            return m.group(1).strip()
        m = re.search(r'"sector"\s*:\s*"([^"]+)"', r.text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def get_sector(ticker: str) -> str:
    """Get GICS sector for a ticker. Static map → DB cache → Zacks scrape."""
    ticker = ticker.upper().strip()
    if not ticker:
        return "Unclassified"

    # 1. Static map
    if ticker in SECTOR_MAP:
        return SECTOR_MAP[ticker]

    # 2. DB cache
    from etf_terminal.db.database import get_cached_sector
    cached = get_cached_sector(ticker)
    if cached:
        return cached

    # 3. Zacks fallback
    sector = _scrape_sector_zacks(ticker)
    if sector:
        from etf_terminal.db.database import cache_sector
        cache_sector(ticker, sector)
        return sector

    return "Unclassified"


def get_sectors_bulk(tickers: list[str], scrape: bool = False) -> dict[str, str]:
    """Batch lookup sectors. Uses static map + cache. Only scrapes if scrape=True."""
    result: dict[str, str] = {}
    to_lookup: list[str] = []

    for t in tickers:
        t = t.upper().strip()
        if not t:
            continue
        if t in SECTOR_MAP:
            result[t] = SECTOR_MAP[t]
        else:
            to_lookup.append(t)

    if not to_lookup:
        return result

    # Check DB cache for all remaining
    from etf_terminal.db.database import get_cached_sectors_bulk
    cached = get_cached_sectors_bulk(to_lookup)
    still_missing: list[str] = []
    for t in to_lookup:
        if t in cached:
            result[t] = cached[t]
        else:
            still_missing.append(t)

    if not scrape:
        for t in still_missing:
            result[t] = "Unclassified"
        return result

    # Scrape only first 20 misses to avoid hammering Zacks
    from etf_terminal.db.database import cache_sector
    for t in still_missing[:20]:
        sector = _scrape_sector_zacks(t)
        if sector:
            cache_sector(t, sector)
            result[t] = sector
        else:
            result[t] = "Unclassified"

    # Anything beyond 20 gets Unclassified
    for t in still_missing[20:]:
        result[t] = "Unclassified"

    return result
