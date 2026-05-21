"""ETF Fees view - expense ratio and fee information."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


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
        import asyncio
        from asyncio import to_thread

        from etfray.data.edgar_service import get_etf_report
        from etfray.data.market_data_service import get_etf_profile, profile_fetched_date
        from etfray.domain.overview_format import fmt_dollars, fmt_expense_ratio, fmt_pct

        content = self.query_one("#fees-content", Static)

        report, profile = await asyncio.gather(
            to_thread(get_etf_report, ticker),
            to_thread(get_etf_profile, ticker),
        )

        if not report and not profile:
            content.loading = False
            content.update(f"Fees — {ticker} (data unavailable)")
            return

        fund_name = ""
        if profile and profile.long_name:
            fund_name = profile.long_name
        elif report and report.fund_name:
            fund_name = report.fund_name

        lines = [
            f"[bold]Fees — {ticker}[/bold]",
            fund_name,
            "",
        ]

        if profile:
            lines.append("── Fees (Yahoo Finance) ──")
            lines.append(f"  Net Expense Ratio:  {fmt_expense_ratio(profile.expense_ratio)}")
            lines.append(f"  Dividend Yield:     {fmt_pct(profile.dividend_yield)}")
            lines.append("")
        else:
            lines.append("  Fee data from Yahoo Finance is unavailable.")
            lines.append("  Check Documents view for latest prospectus/497 filing.")
            lines.append("")

        if report:
            lines.append("── Fund Size (SEC N-PORT) ──")
            lines.append(
                f"  Total Assets:    {fmt_dollars(report.total_assets)}"
                if report.total_assets
                else "  Total Assets:    N/A"
            )
            lines.append(
                f"  Net Assets:      {fmt_dollars(report.net_assets)}"
                if report.net_assets
                else "  Net Assets:      N/A"
            )
            lines.append("")

        lines.append("── Source ──")
        if profile:
            fetched = profile_fetched_date(profile)
            suffix = f" (cached {fetched})" if fetched else ""
            lines.append(f"  Expense ratio: Yahoo Finance{suffix} — not SEC prospectus")
        if report:
            lines.append(f"  AUM: N-PORT filing, period {report.reporting_period}")
        lines.append("  For official fee schedule, see Documents view (N-1A/497).")

        content.loading = False
        content.update("\n".join(lines))
