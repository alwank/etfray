"""ETF Overview view - high-level snapshot of a selected ETF."""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll


class OverviewView(VerticalScroll):
    DEFAULT_CSS = """
    OverviewView {
        padding: 1 2;
    }
    OverviewView .title {
        text-style: bold;
        margin-bottom: 1;
    }
    OverviewView .section {
        margin-top: 1;
        border: solid $primary-background;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Select an ETF from Search to view overview.", id="overview-content")

    def load_etf(self, ticker: str) -> None:
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from etf_terminal.data.edgar_service import get_etf_report, get_holdings_df

        content = self.query_one("#overview-content", Static)
        content.update(f"Loading {ticker}...")

        # Trigger holdings fetch (this will download issuer data if available)
        get_holdings_df(ticker)

        report = get_etf_report(ticker)
        if not report:
            content.update(f"No data available for {ticker}.\nTry searching for a different ETF.")
            return

        # Format dollar amounts
        def fmt_dollars(v) -> str:
            v = float(v)
            if v >= 1_000_000_000:
                return f"${v / 1_000_000_000:.1f}B"
            if v >= 1_000_000:
                return f"${v / 1_000_000:.0f}M"
            return f"${v:,.0f}"

        lines = [
            f"[bold]{ticker} — {report.fund_name}[/bold]",
            f"Issuer: {report.issuer}",
            "",
            "── Key Metrics ──",
            f"  Total Assets:    {fmt_dollars(report.total_assets)}",
            f"  Net Assets:      {fmt_dollars(report.net_assets)}",
            f"  Holdings:        {report.num_holdings:,}",
            "",
            "── Source Provenance ──",
        ]

        # Check if we have issuer daily data
        from etf_terminal.db.database import get_cached_holdings
        from etf_terminal.data.issuer_holdings import is_issuer_supported
        cached = get_cached_holdings(ticker)
        if cached and cached.get("source") == "issuer":
            lines.append(f"  Source:          Issuer daily holdings")
            lines.append(f"  As of:           {cached.get('as_of_date', 'unknown')}")
            lines.append(f"  Freshness:       🟢 Fresh (daily)")
        else:
            lines.append(f"  Source:          N-PORT filing")
            lines.append(f"  Period ended:    {report.reporting_period}")
            lines.append(f"  Filed:           {report.filed_date}")

        if is_issuer_supported(ticker) and not (cached and cached.get("source") == "issuer"):
            lines.append(f"  Daily available: Yes (fetching...)")
        lines.append(f"  CIK:            {report.cik}")
        lines.append(f"  Series ID:      {report.series_id}")

        # Freshness indicator for N-PORT source
        if not (cached and cached.get("source") == "issuer"):
            from datetime import datetime, date
            try:
                as_of = datetime.fromisoformat(str(report.reporting_period)).date()
                days = (date.today() - as_of).days
                if days < 60:
                    freshness = "🟢 Fresh"
                elif days < 150:
                    freshness = "🟡 Acceptable"
                else:
                    freshness = "🔴 Stale"
                lines.insert(3, f"  Data Freshness:  {freshness} ({days} days old)")
            except (ValueError, TypeError):
                pass

        content.update("\n".join(lines))
