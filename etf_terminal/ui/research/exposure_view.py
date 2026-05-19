"""ETF Exposure view - aggregate holdings into exposure categories."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, DataTable, Button
from textual.containers import VerticalScroll

import pandas as pd


class ExposureView(VerticalScroll):
    DEFAULT_CSS = """
    ExposureView {
        padding: 1 2;
    }
    ExposureView Horizontal {
        height: auto;
    }
    ExposureView .exposure-table {
        height: auto;
        width: 1fr;
    }
    """

    _ticker: str = ""
    _sector_data: list = []
    _country_data: list = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Exposure — Select an ETF first", id="exposure-title")
            yield Button("Export", id="export-exposure", variant="success")
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-exposure":
            self._export()

    def load_etf(self, ticker: str) -> None:
        self._ticker = ticker
        self.query_one("#sector-table", DataTable).loading = True
        self.query_one("#country-table", DataTable).loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread
        from etf_terminal.data.edgar_service import get_holdings_df
        from etf_terminal.data.source_resolver import get_freshness_comparison
        from etf_terminal.domain.etf_analytics import calculate_exposure

        title = self.query_one("#exposure-title", Static)
        badge = get_freshness_comparison(ticker)
        badge_str = f" │ {badge}" if badge else ""
        title.update(f"Exposure — {ticker}{badge_str}")

        df = await to_thread(get_holdings_df, ticker)
        if df is None or df.empty:
            title.update(f"Exposure — {ticker} (unavailable)")
            self.query_one("#sector-table", DataTable).loading = False
            self.query_one("#country-table", DataTable).loading = False
            return

        # Asset type exposure
        self._sector_data = calculate_exposure(df, "asset_category")
        st = self.query_one("#sector-table", DataTable)
        st.clear()
        for e in self._sector_data:
            st.add_row(e.category, f"{e.weight:.1f}%", str(e.count))
        st.loading = False

        # Country exposure
        self._country_data = calculate_exposure(df, "investment_country")
        ct = self.query_one("#country-table", DataTable)
        ct.clear()
        for e in self._country_data:
            ct.add_row(e.category, f"{e.weight:.1f}%", str(e.count))
        ct.loading = False

    def _export(self) -> None:
        rows = []
        for e in self._sector_data:
            rows.append({"group": "Asset Type", "category": e.category, "weight_pct": e.weight, "count": e.count})
        for e in self._country_data:
            rows.append({"group": "Country", "category": e.category, "weight_pct": e.weight, "count": e.count})
        if not rows:
            self.app.notify("No data to export", severity="warning")
            return
        df = pd.DataFrame(rows)
        from etf_terminal.data.export_service import export_dataframe_csv
        from etf_terminal.db.database import load_settings
        path = export_dataframe_csv(df, f"{self._ticker}_exposure", load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
