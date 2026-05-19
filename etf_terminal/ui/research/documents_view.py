"""ETF Documents view - list SEC filings with user-friendly labels."""

from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from textual.containers import VerticalScroll

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
        padding: 1 2;
    }
    DocumentsView DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Documents — Select an ETF first", id="docs-title")
        yield DataTable(id="docs-table")

    def on_mount(self) -> None:
        table = self.query_one("#docs-table", DataTable)
        table.add_columns("Document Type", "Form", "Filed Date", "Description")
        table.cursor_type = "row"

    def load_etf(self, ticker: str) -> None:
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from etf_terminal.data.edgar_service import get_filings_list

        title = self.query_one("#docs-title", Static)
        table = self.query_one("#docs-table", DataTable)
        table.clear()
        title.update(f"Documents — {ticker}")

        filings = get_filings_list(ticker)
        if not filings:
            title.update(f"Documents — {ticker} (no filings found)")
            return

        for f in filings:
            form = f["form"]
            label = FORM_LABELS.get(form, form)
            table.add_row(label, form, f["filing_date"], f["description"][:40])
