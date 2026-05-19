"""EDGAR data service wrapping edgartools for ETF research."""

from __future__ import annotations

import io
import pandas as pd
from dataclasses import dataclass
from datetime import datetime

from etf_terminal.db.database import (
    load_settings, cache_etf, get_cached_etf, cache_holdings,
    get_cached_holdings, CachedETF,
)


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
        set_identity("etf.terminal@research.local")


def search_etf(query: str) -> list[ETFSearchResult]:
    """Search for ETFs by ticker, name, or issuer."""
    from etf_terminal.db.database import search_cached_etfs

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
                issuer = company.name.split(" ")[0] if company.name else ""

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
                except Exception:
                    pass

                results.append(ETFSearchResult(
                    ticker=query.upper(),
                    fund_name=fund_name,
                    issuer=issuer.split(" ")[0] if issuer else "",
                    cik=str(company.cik),
                ))
                seen_tickers.add(query.upper())
                cache_etf(CachedETF(
                    ticker=query.upper(),
                    cik=str(company.cik),
                    fund_name=fund_name,
                    issuer=issuer.split(" ")[0] if issuer else "",
                    last_updated=datetime.now().isoformat(),
                ))
                return results
        except Exception:
            pass

    # Search local cache (fast, works for name/issuer)
    cached = search_cached_etfs(query)
    for c in cached:
        if c.ticker not in seen_tickers:
            results.append(ETFSearchResult(
                ticker=c.ticker, fund_name=c.fund_name,
                issuer=c.issuer, cik=c.cik,
            ))
            seen_tickers.add(c.ticker)

    # Search SEC company_tickers.json for name/issuer matches
    if len(results) < 10:
        try:
            matches = _search_sec_tickers(query)
            for ticker, name, cik in matches:
                if ticker not in seen_tickers:
                    results.append(ETFSearchResult(
                        ticker=ticker, fund_name=name,
                        issuer=name.split(" ")[0] if name else "", cik=cik,
                    ))
                    seen_tickers.add(ticker)
                    if len(results) >= 20:
                        break
        except Exception:
            pass

    return results


def _search_sec_tickers(query: str) -> list[tuple[str, str, str]]:
    """Search SEC for fund tickers matching a name/issuer query.

    Uses EDGAR company search to find trust CIKs, then cross-references
    with company_tickers_mf.json to get individual fund tickers.
    """
    import httpx
    import json
    import re
    import time
    from pathlib import Path

    cache_dir = Path.home() / ".etf_terminal" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "etf.terminal@research.local"}

    # Load mutual fund tickers (cached)
    mf_path = cache_dir / "company_tickers_mf.json"
    mf_data = None
    if mf_path.exists() and (time.time() - mf_path.stat().st_mtime) < 7 * 86400:
        mf_data = json.loads(mf_path.read_text())
    else:
        try:
            r = httpx.get("https://www.sec.gov/files/company_tickers_mf.json", headers=headers, timeout=15)
            if r.status_code == 200:
                mf_data = r.json()
                mf_path.write_text(r.text)
        except Exception:
            pass

    if not mf_data or not mf_data.get("data"):
        return []

    # Search EDGAR company search for trust CIKs matching query
    try:
        r = httpx.get(
            "https://www.sec.gov/cgi-bin/browse-edgar",
            params={
                "company": query, "CIK": "", "type": "NPORT-P",
                "owner": "include", "count": "20", "action": "getcompany", "output": "atom",
            },
            headers=headers, timeout=10, follow_redirects=True,
        )
        if r.status_code != 200:
            return []
    except Exception:
        return []

    # Extract CIKs from response
    ciks = {int(c) for c in re.findall(r"<cik>0*(\d+)</cik>", r.text)}
    if not ciks:
        return []

    # Get fund tickers for these CIKs from MF data
    matches: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for row in mf_data["data"]:
        cik_val, series_id, class_id, ticker = row[0], row[1], row[2], row[3]
        if cik_val in ciks and ticker and ticker not in seen:
            # Use series_id as a proxy for fund name (best we have)
            matches.append((ticker, f"{query.title()} Fund ({series_id})", str(cik_val)))
            seen.add(ticker)
            if len(matches) >= 20:
                break

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
        cache_etf(CachedETF(
            ticker=ticker.upper(),
            cik=str(company.cik),
            series_id=series_id,
            fund_name=fund_name or company.name,
            issuer=issuer,
            last_updated=datetime.now().isoformat(),
        ))

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
    except Exception as e:
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
        except Exception:
            pass

    # 2. Fetch from N-PORT via EDGAR
    from edgar import Company

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
            results.append({
                "form": getattr(f, "form", ""),
                "filing_date": str(getattr(f, "filing_date", "")),
                "accession_number": getattr(f, "accession_number", "") or getattr(f, "accession_no", ""),
                "description": getattr(f, "description", "") or "",
            })
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
    from edgar import Company
    import re

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
            if in_risk_section and re.match(r"^(performance|fees|expense|investment\s+objective|portfolio\s+manager)", lower):
                if current_title:
                    risks.append(RiskDisclosure(
                        title=current_title,
                        summary=" ".join(current_body)[:200],
                        source_form=form_type,
                        filed_date=filed_date,
                    ))
                break

            # Detect risk sub-headings (short lines ending with Risk/Risk.)
            if stripped and len(stripped) < 80 and re.search(r"risk\.?$", lower):
                # Save previous
                if current_title:
                    risks.append(RiskDisclosure(
                        title=current_title,
                        summary=" ".join(current_body)[:200],
                        source_form=form_type,
                        filed_date=filed_date,
                    ))
                current_title = stripped.rstrip(".")
                current_body = []
            elif stripped and current_title:
                current_body.append(stripped)

            if len(risks) >= 15:
                break

        # Save last one
        if current_title and len(risks) < 15:
            risks.append(RiskDisclosure(
                title=current_title,
                summary=" ".join(current_body)[:200],
                source_form=form_type,
                filed_date=filed_date,
            ))

        return risks
    except Exception:
        return []
