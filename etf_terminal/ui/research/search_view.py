"""ETF Search view with input and results table."""

from textual.app import ComposeResult
from textual.widgets import Static, Input, DataTable
from textual.containers import VerticalScroll


class SearchView(VerticalScroll):
    DEFAULT_CSS = """
    SearchView {
        padding: 1 2;
    }
    SearchView Input {
        margin-bottom: 1;
    }
    SearchView DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Search ETF / Fund / Issuer")
        yield Input(placeholder="Enter ticker, fund name, or issuer...", id="search-input")
        yield Static("", id="search-status")
        yield DataTable(id="search-results")

    def on_mount(self) -> None:
        table = self.query_one("#search-results", DataTable)
        table.add_columns("Ticker", "Fund Name", "Issuer")
        table.cursor_type = "row"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input" and event.value.strip():
            self._do_search(event.value.strip())

    def _do_search(self, query: str) -> None:
        table = self.query_one("#search-results", DataTable)
        table.loading = True
        self.run_worker(self._search_worker(query), name="search", exclusive=True)

    async def _search_worker(self, query: str) -> None:
        from asyncio import to_thread
        from etf_terminal.data.edgar_service import search_etf

        table = self.query_one("#search-results", DataTable)
        status = self.query_one("#search-status", Static)
        table.clear()
        status.update("")

        results = await to_thread(search_etf, query)
        for r in results:
            table.add_row(r.ticker, r.fund_name[:40], r.issuer, key=r.ticker)

        if results:
            status.update(f"Found {len(results)} result{'s' if len(results) != 1 else ''}")
        else:
            table.add_row("—", "No results found", "")
            status.update("")

        table.loading = False

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and str(event.row_key.value) != "—":
            self.app.navigate_to_etf(str(event.row_key.value))
