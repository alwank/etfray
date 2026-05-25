"""ETF Documents view - list SEC filings with user-friendly labels."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
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
    DocumentsView #docs-body {
        display: none;
    }
    DocumentsView #docs-empty Button {
        margin-top: 1;
    }
    DocumentsView #docs-body Horizontal {
        height: auto;
    }
    DocumentsView DataTable {
        height: auto;
    }
    """

    _ticker: str = ""
    _filings: list[dict] = []
    _cik: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="docs-empty"):
            yield Static("Documents — Select an ETF first")
            yield Button("Open Search to select an ETF →", id="docs-open-search", variant="primary")
        with Vertical(id="docs-body"):
            with Horizontal():
                yield Static("", id="docs-title")
                yield Button("Export", id="export-docs")
            yield DataTable(id="docs-table")

    def on_mount(self) -> None:
        table = self.query_one("#docs-table", DataTable)
        table.add_columns("Document Type", "Form", "Filed Date", "Link")
        table.cursor_type = "row"

    def load_etf(self, ticker: str) -> None:
        self._ticker = ticker
        self.query_one("#docs-empty").display = False
        self.query_one("#docs-body").display = True
        self.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "docs-open-search":
            self.app.navigate_to("research-search")
        elif event.button.id == "export-docs":
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

        self._cik = filings[0].get("cik", "")

        for f in filings:
            form = f["form"]
            label = FORM_LABELS.get(form, form)
            acc = f.get("accession_number", "")
            cik = f.get("cik", "") or self._cik
            link = "↗ Open" if (acc and cik) else "—"
            table.add_row(label, form, f["filing_date"], link, key=acc or None)

        title.update(f"Documents — {ticker}  [Enter] Open in EDGAR")
        self.loading = False

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the selected filing's EDGAR index page in the default browser."""
        row_idx = event.cursor_row
        if not self._filings or row_idx < 0 or row_idx >= len(self._filings):
            return
        filing = self._filings[row_idx]
        accession_number = filing.get("accession_number", "")
        cik = filing.get("cik", "") or self._cik
        if not accession_number or not cik:
            self.app.notify("No URL available for this filing", severity="warning")
            return
        url = self._build_filing_url(accession_number, cik)
        import webbrowser

        webbrowser.open(url)
        self.app.notify(f"Opening {url}")

    def _build_filing_url(self, accession_number: str, cik: str) -> str:
        acc_nodash = accession_number.replace("-", "")
        # The Archives path uses the FILER CIK (first segment of accession number),
        # which may differ from the company CIK when a filing agent submitted on
        # their behalf.  Fall back to the company CIK if parsing fails.
        try:
            filer_cik = str(int(accession_number.split("-")[0]))
        except (ValueError, IndexError):
            filer_cik = str(int(cik)) if cik.isdigit() else cik
        return f"https://www.sec.gov/Archives/edgar/data/{filer_cik}/{acc_nodash}/{accession_number}-index.htm"

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
