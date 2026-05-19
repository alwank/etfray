"""ETF Concentration view - top N weights, HHI, effective holdings."""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll


class ConcentrationView(VerticalScroll):
    DEFAULT_CSS = """
    ConcentrationView {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Concentration — Select an ETF first", id="conc-content")

    def load_etf(self, ticker: str) -> None:
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from etf_terminal.data.edgar_service import get_holdings_df
        from etf_terminal.domain.etf_analytics import calculate_concentration

        content = self.query_one("#conc-content", Static)
        content.update(f"Loading concentration for {ticker}...")

        df = get_holdings_df(ticker)
        if df is None or df.empty:
            content.update(f"Concentration — {ticker} (holdings unavailable)")
            return

        m = calculate_concentration(df)

        hhi_label = "Low" if m.hhi < 0.01 else "Medium" if m.hhi < 0.05 else "High"

        lines = [
            f"[bold]Concentration — {ticker}[/bold]",
            "",
            f"  Number of holdings:    {m.num_holdings:,}",
            f"  Largest holding:       {m.largest_holding} ({m.top1_weight:.2f}%)",
            f"  Top 5 holdings:        {m.top5_weight:.1f}%",
            f"  Top 10 holdings:       {m.top10_weight:.1f}%",
            f"  Top 25 holdings:       {m.top25_weight:.1f}%",
            f"  Top 50 holdings:       {m.top50_weight:.1f}%",
            "",
            f"  Effective holdings:    {m.effective_n:.0f}",
            f"  HHI:                   {m.hhi:.6f} ({hhi_label})",
            f"  Verdict:               {m.verdict}",
        ]
        content.update("\n".join(lines))
