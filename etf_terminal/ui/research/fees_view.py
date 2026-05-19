"""ETF Fees view - expense ratio and fee information."""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll


class FeesView(VerticalScroll):
    DEFAULT_CSS = """
    FeesView {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Fees — Select an ETF first", id="fees-content")

    def load_etf(self, ticker: str) -> None:
        content = self.query_one("#fees-content", Static)
        content.update("")
        content.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread
        content = self.query_one("#fees-content", Static)

        # Fee data typically comes from prospectus (N-1A/497)
        # edgartools doesn't directly parse expense ratios from N-1A yet,
        # so we show what's available from N-PORT fund_info
        from etf_terminal.data.edgar_service import get_etf_report

        report = await to_thread(get_etf_report, ticker)
        if not report:
            content.loading = False
            content.update(f"Fees — {ticker} (data unavailable)")
            return

        lines = [
            f"[bold]Fees — {ticker}[/bold]",
            f"{report.fund_name}",
            "",
            "  Fee data from prospectus parsing is limited.",
            "  Check Documents view for latest prospectus/497 filing.",
            "",
            "── Available Fund Data ──",
            f"  Total Assets:    ${report.total_assets:,.0f}" if report.total_assets else "  Total Assets:    N/A",
            f"  Net Assets:      ${report.net_assets:,.0f}" if report.net_assets else "  Net Assets:      N/A",
            "",
            "── Source ──",
            f"  Source: N-PORT filing, period {report.reporting_period}",
            "  For expense ratio, see latest N-1A or 497 filing.",
        ]
        content.loading = False
        content.update("\n".join(lines))
