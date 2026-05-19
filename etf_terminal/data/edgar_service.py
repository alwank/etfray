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
    _ensure_identity()
    from edgar import Company, find

    results: list[ETFSearchResult] = []

    # Try direct ticker lookup first
    try:
        company = Company(query.upper())
        if company:
            results.append(ETFSearchResult(
                ticker=query.upper(),
                fund_name=company.name,
                issuer=company.name.split(" ")[0] if company.name else "",
                cik=str(company.cik),
            ))
            # Cache it
            cache_etf(CachedETF(
                ticker=query.upper(),
                cik=str(company.cik),
                fund_name=company.name,
                issuer=company.name.split(" ")[0] if company.name else "",
                last_updated=datetime.now().isoformat(),
            ))
            return results
    except Exception:
        pass

    # Fallback to text search
    try:
        matches = find(query)
        if matches is not None:
            for match in matches[:10]:
                name = getattr(match, "name", "") or getattr(match, "company", "") or str(match)
                cik = str(getattr(match, "cik", ""))
                ticker_val = getattr(match, "ticker", "") or getattr(match, "tickers", [""])[0] if hasattr(match, "tickers") else ""
                results.append(ETFSearchResult(
                    ticker=ticker_val or query.upper(),
                    fund_name=name,
                    issuer=name.split(" ")[0] if name else "",
                    cik=cik,
                ))
    except Exception:
        pass

    return results


def get_etf_report(ticker: str) -> ETFReport | None:
    """Get N-PORT report data for an ETF."""
    _ensure_identity()
    from edgar import Company

    try:
        company = Company(ticker.upper())
        filings = company.get_filings(form="NPORT-P")
        if not filings or len(filings) == 0:
            return None

        filing = filings[0]
        report = filing.obj()

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
    """Get holdings DataFrame — prefers issuer daily data, falls back to N-PORT."""
    _ensure_identity()
    from datetime import date as date_cls

    ticker = ticker.upper()
    today = date_cls.today().isoformat()

    # 1. Check cache — if cached today from issuer, use it
    cached = get_cached_holdings(ticker)
    if cached and cached.get("source") == "issuer" and cached.get("as_of_date") == today:
        try:
            return pd.read_json(io.StringIO(cached["holdings_json"]))
        except Exception:
            pass

    # 2. Try issuer daily download
    from etf_terminal.data.issuer_holdings import get_issuer_holdings, is_issuer_supported

    if is_issuer_supported(ticker):
        df = get_issuer_holdings(ticker)
        if df is not None and not df.empty:
            cache_holdings(ticker, df.to_json(), today, today, source="issuer")
            return df

    # 3. Check cache — any cached data (even stale) before hitting EDGAR
    if cached and cached.get("holdings_json"):
        try:
            return pd.read_json(io.StringIO(cached["holdings_json"]))
        except Exception:
            pass

    # 4. Fall back to N-PORT via EDGAR
    from edgar import Company

    try:
        company = Company(ticker)
        filings = company.get_filings(form="NPORT-P")
        if not filings or len(filings) == 0:
            return None

        report = filings[0].obj()
        df = report.investment_data()
        if df is None or df.empty:
            return None

        as_of = str(getattr(report, "reporting_period", ""))
        filed = str(getattr(filings[0], "filing_date", ""))
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
