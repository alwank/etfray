"""Overview view formatting helpers."""

from __future__ import annotations

import textwrap
from datetime import date, datetime

from etfray.data.edgar_service import ETFReport
from etfray.data.market_data_service import ETFProfile, get_profile_last_error, profile_fetched_date
from etfray.domain.etf_analytics import ConcentrationMetrics, ExposureBreakdown


def fmt_dollars(v) -> str:
    v = float(v)
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.0f}M"
    return f"${v:,.0f}"


def fmt_pct(v, *, signed: bool = False, decimals: int = 2) -> str:
    if v is None:
        return "N/A"
    pct = float(v) * 100
    if signed and pct > 0:
        return f"+{pct:.{decimals}f}%"
    return f"{pct:.{decimals}f}%"


def fmt_expense_ratio(v) -> str:
    if v is None:
        return "N/A"
    return f"{float(v) * 100:.2f}%"


def fmt_number(v) -> str:
    if v is None:
        return "N/A"
    n = float(v)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:,.0f}K"
    return f"{n:,.0f}"


def wrap_description(text: str, width: int = 72, indent: str = "  ") -> list[str]:
    if not text:
        return []
    wrapped = textwrap.wrap(text.strip(), width=width)
    return [f"{indent}{line}" for line in wrapped]


def _freshness_label(reporting_period: str, fresh_days: int, acceptable_days: int) -> str | None:
    try:
        as_of = datetime.fromisoformat(str(reporting_period)).date()
        days = (date.today() - as_of).days
        if days < fresh_days:
            freshness = "🟢 Fresh"
        elif days < acceptable_days:
            freshness = "🟡 Acceptable"
        else:
            freshness = "🔴 Stale"
        return f"  Data Freshness:  {freshness} ({days} days old)"
    except (ValueError, TypeError):
        return None


def _display_name(ticker: str, report: ETFReport | None, profile: ETFProfile | None) -> str:
    if profile and profile.long_name:
        return profile.long_name
    if report and report.fund_name:
        return report.fund_name
    if profile and profile.short_name:
        return profile.short_name
    return ticker


def _issuer_line(report: ETFReport | None, profile: ETFProfile | None) -> str:
    parts: list[str] = []
    if report and report.issuer:
        parts.append(f"Issuer: {report.issuer} (EDGAR)")
    if profile and profile.fund_family:
        if report and report.issuer and report.issuer.lower() == profile.fund_family.lower():
            return f"Issuer: {report.issuer}"
        parts.append(f"Fund Family: {profile.fund_family} (Yahoo)")
    if not parts:
        return ""
    return " / ".join(parts) if len(parts) > 1 else parts[0]


def format_overview_lines(
    ticker: str,
    report: ETFReport | None,
    profile: ETFProfile | None,
    concentration: ConcentrationMetrics | None,
    top_sector: ExposureBreakdown | None,
    freshness_badge: str | None,
    *,
    fresh_days: int = 30,
    acceptable_days: int = 90,
) -> list[str]:
    if not report and not profile:
        return [f"No data available for {ticker}.", "Try searching for a different ETF."]

    lines: list[str] = [
        f"[bold]{ticker} — {_display_name(ticker, report, profile)}[/bold]",
    ]

    issuer_line = _issuer_line(report, profile)
    if issuer_line:
        lines.append(issuer_line)
    lines.append("")

    if profile:
        lines.append("── Fund Profile (Yahoo Finance) ──")
        if profile.category:
            lines.append(f"  Category:        {profile.category}")
        if profile.inception_date:
            lines.append(f"  Inception:       {profile.inception_date}")
        if profile.expense_ratio is not None:
            lines.append(f"  Expense Ratio:   {fmt_expense_ratio(profile.expense_ratio)}")
        if profile.dividend_yield is not None:
            lines.append(f"  Dividend Yield:  {fmt_pct(profile.dividend_yield)}")
        if profile.beta is not None:
            lines.append(f"  Beta (3Y):       {profile.beta:.2f}")

        returns: list[str] = []
        if profile.ytd_return is not None:
            returns.append(f"YTD {fmt_pct(profile.ytd_return, signed=True)}")
        if profile.return_3y is not None:
            returns.append(f"3Y {fmt_pct(profile.return_3y, signed=True)}")
        if profile.return_5y is not None:
            returns.append(f"5Y {fmt_pct(profile.return_5y, signed=True)}")
        if returns:
            lines.append(f"  Returns:         {' | '.join(returns)}")

        market_bits: list[str] = []
        if profile.exchange:
            market_bits.append(f"Exchange: {profile.exchange}")
        if profile.avg_volume is not None:
            market_bits.append(f"Avg Vol: {fmt_number(profile.avg_volume)}")
        if profile.nav_price is not None:
            market_bits.append(f"NAV: ${profile.nav_price:,.2f}")
        if market_bits:
            lines.append(f"  {' | '.join(market_bits)}")

        if profile.description:
            lines.append("")
            lines.extend(wrap_description(profile.description))
        lines.append("")
    elif report:
        lines.append("  Fund profile unavailable (Yahoo Finance).")
        err = get_profile_last_error()
        if err:
            lines.append(f"  Reason: {err}")
        else:
            lines.append("  Yahoo may be rate-limited — reopen the ETF or try again shortly.")
        lines.append("")

    if report:
        lines.append("── Key Metrics (SEC N-PORT) ──")
        if report.total_assets:
            lines.append(f"  Total Assets:    {fmt_dollars(report.total_assets)}")
        if report.net_assets:
            lines.append(f"  Net Assets:      {fmt_dollars(report.net_assets)}")
        if report.num_holdings:
            lines.append(f"  Holdings:        {report.num_holdings:,}")

        freshness = _freshness_label(report.reporting_period, fresh_days, acceptable_days)
        if freshness:
            lines.append(freshness)
        lines.append("")
    elif profile:
        lines.append("── Key Metrics (SEC N-PORT) ──")
        lines.append("  N-PORT data unavailable.")
        lines.append("")

    if concentration and concentration.num_holdings > 0:
        lines.append("── Portfolio Shape (computed) ──")
        lines.append(f"  Top 10 Weight:   {concentration.top10_weight:.1f}%")
        lines.append(f"  Effective N:     {concentration.effective_n:.0f}")
        if top_sector:
            lines.append(f"  Largest Sector:  {top_sector.category} ({top_sector.weight:.1f}%)")
        lines.append("")

    lines.append("── Source Provenance ──")
    if report:
        lines.append("  Holdings Source: N-PORT filing")
        lines.append(f"  Period ended:    {report.reporting_period}")
        lines.append(f"  Filed:           {report.filed_date}")
        lines.append(f"  CIK:             {report.cik}")
        if report.series_id:
            lines.append(f"  Series ID:       {report.series_id}")
    if profile:
        fetched = profile_fetched_date(profile)
        if fetched:
            lines.append(f"  Profile Source:  Yahoo Finance (cached {fetched})")
    if freshness_badge:
        lines.append(f"  {freshness_badge}")

    return lines
