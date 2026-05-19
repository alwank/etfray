"""ETF Exposure view - aggregate holdings into exposure categories."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, DataTable
from textual.containers import VerticalScroll


class ExposureView(VerticalScroll):
    DEFAULT_CSS = """
    ExposureView {
        padding: 1 2;
    }
    ExposureView .exposure-table {
        height: 1fr;
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Exposure — Select an ETF first", id="exposure-title")
        with Horizontal():
            yield DataTable(id="sector-table", classes="exposure-table")
            yield DataTable(id="country-table", classes="exposure-table")

    def on_mount(self) -> None:
        st = self.query_one("#sector-table", DataTable)
        st.add_columns("Asset Type", "Weight %", "Count")
        st.cursor_type = "row"

        ct = self.query_one("#country-table", DataTable)
        ct.add_columns("Country", "Weight %", "Count")
        ct.cursor_type = "row"

    def load_etf(self, ticker: str) -> None:
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from etf_terminal.data.edgar_service import get_holdings_df
        from etf_terminal.data.source_resolver import get_freshness_comparison
        from etf_terminal.domain.etf_analytics import calculate_exposure

        title = self.query_one("#exposure-title", Static)
        badge = get_freshness_comparison(ticker)
        badge_str = f" │ {badge}" if badge else ""
        title.update(f"Exposure — {ticker}{badge_str}")

        df = get_holdings_df(ticker)
        if df is None or df.empty:
            title.update(f"Exposure — {ticker} (unavailable)")
            return

        # Asset type exposure
        st = self.query_one("#sector-table", DataTable)
        st.clear()
        for e in calculate_exposure(df, "asset_category"):
            st.add_row(e.category, f"{e.weight:.1f}%", str(e.count))

        # Country exposure
        ct = self.query_one("#country-table", DataTable)
        ct.clear()
        for e in calculate_exposure(df, "investment_country"):
            ct.add_row(e.category, f"{e.weight:.1f}%", str(e.count))
