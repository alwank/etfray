"""EDGAR data service wrapping edgartools for ETF research."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from etfray.db.database import (
    CachedETF,
    cache_etf,
    cache_holdings,
    get_cached_holdings,
    load_settings,
)

_log = logging.getLogger(__name__)


@dataclass
class ETFSearchResult:
    ticker: str
    fund_name: str
    issuer: str
    cik: str
    has_filings: bool = True


@dataclass
class ETFReport:
    ticker: str
    fund_name: str
    issuer: str
    cik: str
    series_id: str
    total_assets: float
    net_assets: float
    num_holdings: int
    reporting_period: str
    filed_date: str


def _ensure_identity() -> None:
    from edgar import set_identity

    s = load_settings()
    if s.edgar_identity:
        set_identity(s.edgar_identity)
    else:
        raise RuntimeError(
            "EDGAR identity not configured. Open Settings and enter a valid "
            "contact email (required by SEC fair-access policy)."
        )


def search_etf(query: str) -> list[ETFSearchResult]:
    """Search for ETFs by ticker, name, or issuer."""
    from etfray.db.database import search_cached_etfs

    _ensure_identity()
    from edgar import Company

    results: list[ETFSearchResult] = []
    seen_tickers: set[str] = set()

    # Try direct ticker lookup first (only if query looks like a ticker)
    if len(query.split()) == 1 and query.upper().isalpha() and len(query) <= 5:
        try:
            company = Company(query.upper())
            if company:
                fund_name = company.name
                issuer = company.name or ""

                try:
                    filings = company.get_filings(form="NPORT-P")
                    if filings and len(filings) > 0:
                        head = filings.head(150)
                        for f in head:
                            r = f.obj()
                            if hasattr(r, "matches_ticker") and r.matches_ticker(query.upper()):
                                gi = r.general_info
                                fund_name = gi.series_name or fund_name
                                issuer = getattr(gi, "name", issuer) or issuer
                                break
                except Exception as exc:
                    _log.debug("EDGAR filings scan for %s: %s", query, exc)

                results.append(
                    ETFSearchResult(
                        ticker=query.upper(),
                        fund_name=fund_name,
                        issuer=issuer,
                        cik=str(company.cik),
                    )
                )
                seen_tickers.add(query.upper())
                cache_etf(
                    CachedETF(
                        ticker=query.upper(),
                        cik=str(company.cik),
                        fund_name=fund_name,
                        issuer=issuer,
                        last_updated=datetime.now().isoformat(),
                    )
                )
                return results
        except Exception as exc:
            _log.debug("EDGAR direct ticker lookup failed for %s: %s", query, exc)

    # Search local cache (fast, works for name/issuer)
    cached = search_cached_etfs(query)
    for c in cached:
        if c.ticker not in seen_tickers:
            results.append(
                ETFSearchResult(
                    ticker=c.ticker,
                    fund_name=c.fund_name,
                    issuer=c.issuer,
                    cik=c.cik,
                )
            )
            seen_tickers.add(c.ticker)

    # Search SEC Series & Class CSV for name/issuer matches
    try:
        matches = _search_sec_tickers(query)
        for ticker, name, cik, issuer in matches:
            if ticker not in seen_tickers:
                results.append(
                    ETFSearchResult(
                        ticker=ticker,
                        fund_name=name,
                        issuer=issuer,
                        cik=cik,
                    )
                )
                seen_tickers.add(ticker)
                cache_etf(
                    CachedETF(
                        ticker=ticker,
                        cik=cik,
                        fund_name=name,
                        issuer=issuer,
                        last_updated=datetime.now().isoformat(),
                    )
                )
    except Exception as exc:
        _log.warning("SEC CSV ticker search failed: %s", exc)

    return results


def _load_series_class_csv() -> list[dict] | None:
    """Download and cache the SEC Investment Company Series & Class CSV."""
    import csv
    import time
    from pathlib import Path

    import httpx

    cache_dir = Path.home() / ".etfray" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / "sec_series_class.csv"
    headers = {"User-Agent": load_settings().edgar_identity or "etfray-app/1.0"}

    if not csv_path.exists() or (time.time() - csv_path.stat().st_mtime) > 7 * 86400:
        try:
            r = httpx.get(
                f"https://www.sec.gov/files/investment/data/other/investment-company-series-class-information/investment-company-series-class-{str(datetime.now().year)}.csv",
                headers=headers,
                timeout=30,
                follow_redirects=True,
            )
            if r.status_code == 200:
                csv_path.write_bytes(r.content)
            else:
                if not csv_path.exists():
                    return None
        except Exception:
            if not csv_path.exists():
                return None
            _log.warning(
                "_load_series_class_csv: GET failed; falling back to stale cached file at %s",
                csv_path,
            )

    try:
        rows = []
        with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = (row.get("Class Ticker") or row.get("TICKER") or row.get("ticker") or "").strip()
                if ticker:
                    rows.append(
                        {
                            "cik": (row.get("CIK Number") or row.get("CIK") or row.get("cik") or "").strip(),
                            "series_id": (row.get("Series ID") or row.get("SERIES_ID") or "").strip(),
                            "series_name": (row.get("Series Name") or row.get("SERIES_NAME") or "").strip(),
                            "class_name": (row.get("Class Name") or row.get("CLASS_NAME") or "").strip(),
                            "ticker": ticker,
                            "registrant": (
                                row.get("Entity Name") or row.get("REGISTRANT_NAME") or row.get("COMPANY_NAME") or ""
                            ).strip(),
                        }
                    )
        return rows
    except Exception:
        return None


@dataclass
class ETFUniverseEntry:
    ticker: str
    fund_name: str
    issuer: str
    cik: str
    asset_class: str
    category: str
    geography: str


_universe_cache: list[ETFUniverseEntry] | None = None


def invalidate_universe_cache() -> None:
    """Clear the in-memory ETF universe cache so the next call re-parses from disk."""
    global _universe_cache
    _universe_cache = None


def _classify_etf(series_name: str, registrant: str) -> tuple[str, str, str]:
    """Infer (asset_class, category, geography) from fund name keywords.

    Returns best-effort labels; falls back to 'Equity', 'Broad Market', 'US'.
    """
    name = (series_name + " " + registrant).lower()

    # Asset class
    if any(
        k in name
        for k in (
            "bond",
            "treasury",
            "fixed income",
            "tips",
            "credit",
            "note",
            "debt",
            "municipal",
            "muni",
            "yield",
            "income fund",
            "aggregate",
        )
    ):
        asset_class = "Fixed Income"
    elif any(
        k in name
        for k in (
            "gold",
            "silver",
            "oil",
            "commodity",
            "commodities",
            "metal",
            "copper",
            "natural gas",
            "energy fund",
            "agriculture",
        )
    ):
        asset_class = "Commodity"
    elif any(
        k in name for k in ("multi-asset", "allocation", "balanced", "managed futures", "real return", "inflation")
    ):
        asset_class = "Multi-Asset"
    elif any(k in name for k in ("real estate", "reit", "property", "mortgage")):
        asset_class = "Real Estate"
    else:
        asset_class = "Equity"

    # Category
    _sector_keywords = (
        "technology",
        "tech",
        "health",
        "healthcare",
        "energy",
        "financials",
        "financial",
        "utilities",
        "industrial",
        "consumer",
        "materials",
        "communication",
        "semiconductor",
        "biotech",
        "bank",
        "insurance",
        "retail",
        "aerospace",
        "defense",
        "clean energy",
        "solar",
        "cyber",
        "cloud",
        "ai ",
        "artificial intelligence",
    )
    _factor_keywords = (
        "dividend",
        "growth",
        "value",
        "quality",
        "momentum",
        "low volatility",
        "min vol",
        "multifactor",
        "factor",
        "esg",
        "sustainable",
        "responsible",
    )

    if asset_class == "Fixed Income":
        category = "Fixed Income"
    elif asset_class == "Commodity":
        category = "Commodity"
    elif asset_class == "Real Estate":
        category = "Real Estate"
    elif asset_class == "Multi-Asset":
        category = "Multi-Asset"
    elif any(k in name for k in _sector_keywords):
        category = "Sector / Thematic"
    elif any(k in name for k in _factor_keywords):
        category = "Factor / Smart Beta"
    elif any(
        k in name
        for k in (
            "s&p 500",
            "total market",
            "total stock",
            "broad market",
            "all cap",
            "large cap",
            "mid cap",
            "small cap",
            "extended market",
            "russell",
            "nasdaq",
            "dow",
        )
    ):
        category = "Broad Market"
    elif any(k in name for k in ("leveraged", "2x", "3x", "ultra", "inverse", "short ")):
        category = "Leveraged / Inverse"
    elif any(k in name for k in ("currency", "forex", "fx ")):
        category = "Currency"
    else:
        category = "Broad Market"

    # Geography
    _intl_keywords = (
        "international",
        "world",
        "global",
        "developed markets",
        "msci eafe",
        "eafe",
        "europe",
        "pacific",
        "acwi",
        "acwx",
    )
    _em_keywords = (
        "emerging",
        "emerging markets",
        "em ",
        "bric",
        "latin america",
        "asia",
        "china",
        "india",
        "brazil",
        "korea",
        "taiwan",
        "mexico",
        "africa",
        "frontier",
    )
    _single_country = (
        "germany",
        "japan",
        "uk ",
        "united kingdom",
        "australia",
        "canada",
        "france",
        "switzerland",
        "israel",
        "indonesia",
        "vietnam",
        "poland",
        "hungary",
        "turkey",
        "greece",
    )

    if any(k in name for k in _em_keywords):
        geography = "Emerging Markets"
    elif any(k in name for k in _single_country):
        geography = "Single Country"
    elif any(k in name for k in _intl_keywords):
        geography = "International"
    else:
        geography = "US"

    return asset_class, category, geography


def get_etf_universe(*, force_refresh: bool = False) -> list[ETFUniverseEntry]:
    """Return the full ETF universe from the cached SEC Series & Class CSV.

    Results are classified by asset class, category, and geography using
    keyword heuristics on the fund name. The parsed list is cached in memory
    for the lifetime of the process.

    Pass ``force_refresh=True`` to discard the in-memory cache and re-parse
    from disk (or re-download from SEC) before returning.
    """
    global _universe_cache
    if _universe_cache is not None and not force_refresh:
        return _universe_cache

    data = _load_series_class_csv()
    if not data:
        _universe_cache = []
        return _universe_cache

    seen: set[str] = set()
    entries: list[ETFUniverseEntry] = []
    for row in data:
        ticker = row["ticker"]
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        asset_class, category, geography = _classify_etf(row["series_name"], row["registrant"])
        entries.append(
            ETFUniverseEntry(
                ticker=ticker,
                fund_name=row["series_name"] or f"Fund ({row['series_id']})",
                issuer=row["registrant"],
                cik=row["cik"],
                asset_class=asset_class,
                category=category,
                geography=geography,
            )
        )

    _universe_cache = entries
    return _universe_cache


def _search_sec_tickers(query: str) -> list[tuple[str, str, str, str]]:
    """Search SEC Series & Class CSV for funds matching a name/issuer query.

    Returns list of (ticker, fund_name, cik, issuer).
    """
    data = _load_series_class_csv()
    if not data:
        return []

    q = query.lower()
    matches: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()

    for row in data:
        series_name = row["series_name"]
        registrant = row["registrant"]
        ticker = row["ticker"]

        if ticker in seen:
            continue

        if q in series_name.lower() or q in registrant.lower():
            fund_name = series_name or f"Fund ({row['series_id']})"
            issuer = registrant
            matches.append((ticker, fund_name, row["cik"], issuer))
            seen.add(ticker)

    return matches


def _find_nport_for_ticker(ticker: str):
    """Find the correct N-PORT filing for a ticker in a fund family trust."""
    from edgar import Company

    company = Company(ticker)
    filings = company.get_filings(form="NPORT-P")
    if not filings or len(filings) == 0:
        return None, None

    first_filing = filings[0]
    report = first_filing.obj()

    # Check if first filing matches this ticker
    if hasattr(report, "matches_ticker") and report.matches_ticker(ticker):
        return first_filing, report

    # Single-fund trust (no ticker matching available) — use first filing
    if not hasattr(report, "matches_ticker"):
        return first_filing, report

    # Fund family: iterate recent filings to find the matching ticker
    head = filings.head(150)
    for f in head:
        r = f.obj()
        if r.matches_ticker(ticker):
            return f, r

    # Fallback: return first filing
    _log.warning(
        "_find_nport_for_ticker: no filing matched ticker %s in head(150); falling back to first filing",
        ticker,
    )
    return first_filing, report


def get_etf_report(ticker: str) -> ETFReport | None:
    """Get N-PORT report data for an ETF."""
    _ensure_identity()
    from edgar import Company

    try:
        company = Company(ticker.upper())
        filing, report = _find_nport_for_ticker(ticker.upper())
        if not filing or not report:
            return None

        fund_name = ""
        issuer = ""
        series_id = ""
        if hasattr(report, "general_info") and report.general_info:
            fund_name = getattr(report.general_info, "series_name", "") or ""
            issuer = getattr(report.general_info, "name", "") or ""
            series_id = getattr(report.general_info, "series_id", "") or ""

        total_assets = 0.0
        net_assets = 0.0
        if hasattr(report, "fund_info") and report.fund_info:
            total_assets = getattr(report.fund_info, "total_assets", 0) or 0
            net_assets = getattr(report.fund_info, "net_assets", 0) or 0

        # Count holdings
        num_holdings = 0
        try:
            df = report.investment_data()
            if df is not None and not df.empty:
                num_holdings = len(df)
        except Exception:
            pass

        reporting_period = getattr(report, "reporting_period", "") or ""
        filed_date = str(getattr(filing, "filing_date", "")) if filing else ""

        # Cache the ETF info
        cache_etf(
            CachedETF(
                ticker=ticker.upper(),
                cik=str(company.cik),
                series_id=series_id,
                fund_name=fund_name or company.name,
                issuer=issuer,
                last_updated=datetime.now().isoformat(),
            )
        )
        invalidate_universe_cache()

        return ETFReport(
            ticker=ticker.upper(),
            fund_name=fund_name or company.name,
            issuer=issuer,
            cik=str(company.cik),
            series_id=series_id,
            total_assets=total_assets,
            net_assets=net_assets,
            num_holdings=num_holdings,
            reporting_period=str(reporting_period),
            filed_date=filed_date,
        )
    except Exception:
        return None


def get_holdings_df(ticker: str) -> pd.DataFrame | None:
    """Get holdings DataFrame from cache or N-PORT filing."""
    _ensure_identity()
    ticker = ticker.upper()

    # 1. Check cache
    cached = get_cached_holdings(ticker, source="nport")
    if cached and cached.get("holdings_json"):
        try:
            return pd.read_json(io.StringIO(cached["holdings_json"]))
        except Exception as exc:
            _log.debug("Holdings cache read failed for %s: %s", ticker, exc)

    # 2. Fetch from N-PORT via EDGAR

    try:
        filing, report = _find_nport_for_ticker(ticker)
        if not filing or not report:
            return None

        df = report.investment_data()
        if df is None or df.empty:
            return None

        as_of = str(getattr(report, "reporting_period", ""))
        filed = str(getattr(filing, "filing_date", ""))
        cache_holdings(ticker, df.to_json(), as_of, filed, source="nport")
        invalidate_universe_cache()
        return df
    except Exception:
        return None


def get_filings_list(ticker: str, form: str = "") -> list[dict]:
    """Get list of filings for an ETF."""
    _ensure_identity()
    from edgar import Company

    try:
        company = Company(ticker.upper())
        filings = company.get_filings(form=form) if form else company.get_filings()
        results = []
        for f in filings[:20]:
            results.append(
                {
                    "form": getattr(f, "form", ""),
                    "filing_date": str(getattr(f, "filing_date", "")),
                    "accession_number": getattr(f, "accession_number", "") or getattr(f, "accession_no", ""),
                    "description": getattr(f, "description", "") or "",
                }
            )
        return results
    except Exception:
        return []


@dataclass
class RiskDisclosure:
    title: str
    summary: str
    source_form: str
    filed_date: str


def get_risk_disclosures(ticker: str) -> list[RiskDisclosure]:
    """Extract risk factor disclosures from the latest N-1A or 497 filing."""
    _ensure_identity()
    import re

    from edgar import Company

    try:
        company = Company(ticker.upper())

        # Try 497K first (summary prospectus), then 497, then N-1A
        filing = None
        for form in ("497K", "497", "N-1A"):
            filings = company.get_filings(form=form)
            if filings and len(filings) > 0:
                filing = filings[0]
                break

        if not filing:
            return []

        filed_date = str(getattr(filing, "filing_date", ""))
        form_type = getattr(filing, "form", "")

        # Get filing text
        text = ""
        try:
            text = filing.text()
        except Exception:
            try:
                text = str(filing.obj()) if hasattr(filing, "obj") else ""
            except Exception:
                return []

        if not text:
            return []

        # Extract risk sections - look for "Principal Risks" or "Risk" headers
        risks: list[RiskDisclosure] = []
        # Pattern: lines that look like risk factor titles
        # Common patterns: "Market Risk", "Concentration Risk.", "• Market Risk"
        lines = text.split("\n")
        in_risk_section = False
        current_title = ""
        current_body: list[str] = []

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            # Detect start of risk section
            if not in_risk_section:
                if re.match(r"^(principal\s+risks?|risk\s+factors?|fund\s+risks?)", lower):
                    in_risk_section = True
                continue

            # Detect end of risk section (next major heading)
            if in_risk_section and re.match(
                r"^(performance|fees|expense|investment\s+objective|portfolio\s+manager)", lower
            ):
                if current_title:
                    risks.append(
                        RiskDisclosure(
                            title=current_title,
                            summary=" ".join(current_body)[:200],
                            source_form=form_type,
                            filed_date=filed_date,
                        )
                    )
                break

            # Detect risk sub-headings (short lines ending with Risk/Risk.)
            if stripped and len(stripped) < 80 and re.search(r"risk\.?$", lower):
                # Save previous
                if current_title:
                    risks.append(
                        RiskDisclosure(
                            title=current_title,
                            summary=" ".join(current_body)[:200],
                            source_form=form_type,
                            filed_date=filed_date,
                        )
                    )
                current_title = stripped.rstrip(".")
                current_body = []
            elif stripped and current_title:
                current_body.append(stripped)

            if len(risks) >= 15:
                break

        # Save last one
        if current_title and len(risks) < 15:
            risks.append(
                RiskDisclosure(
                    title=current_title,
                    summary=" ".join(current_body)[:200],
                    source_form=form_type,
                    filed_date=filed_date,
                )
            )

        return risks
    except Exception as exc:
        _log.warning("Risk disclosures fetch failed for %s: %s", ticker, exc)
        return []
