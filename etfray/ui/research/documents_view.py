"""ETF Documents view - list SEC filings with user-friendly labels."""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Static

FORM_LABELS = {
    "NPORT-P": "Holdings Report",
    "NPORT-EX": "Holdings Exhibit",
    "N-1A": "Prospectus",
    "N-1A/A": "Prospectus Amendment",
    "497": "Prospectus Supplement",
    "497K": "Summary Prospectus",
    "N-CSR": "Shareholder Report",
    "N-CSRS": "Semi-Annual Report",
    "N-CEN": "Fund Census",
    "N-PX": "Proxy Voting Record",
    "24F-2NT": "Fee Notice",
}


class DocumentsView(VerticalScroll):
    DEFAULT_CSS = """
    DocumentsView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    DocumentsView Horizontal {
        height: auto;
    }
    DocumentsView DataTable {
        height: auto;
    }
    """

    _ticker: str = ""
    _filings: list[dict] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Documents — Select an ETF first", id="docs-title")
            yield Button("Export", id="export-docs", variant="success")
        yield DataTable(id="docs-table")

    def on_mount(self) -> None:
        table = self.query_one("#docs-table", DataTable)
        table.add_columns("Document Type", "Form", "Filed Date", "Description")
        table.cursor_type = "row"

    def load_etf(self, ticker: str) -> None:
        self._ticker = ticker
        self.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-docs":
            self._export()

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread

        from etfray.data.edgar_service import get_filings_list

        title = self.query_one("#docs-title", Static)
        table = self.query_one("#docs-table", DataTable)
        table.clear()
        title.update(f"Documents — {ticker}")

        filings = await to_thread(get_filings_list, ticker)
        self._filings = filings
        if not filings:
            title.update(f"Documents — {ticker} (no filings found)")
            self.loading = False
            return

        for f in filings:
            form = f["form"]
            label = FORM_LABELS.get(form, form)
            table.add_row(label, form, f["filing_date"], f["description"][:40])

        self.loading = False

    def _export(self) -> None:
        if not self._filings:
            self.app.notify("No data to export", severity="warning")
            return
        import pandas as pd

        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings
        df = pd.DataFrame(self._filings)
        path = export_dataframe_csv(df, f"{self._ticker}_documents", load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
