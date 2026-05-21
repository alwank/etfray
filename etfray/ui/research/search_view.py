"""ETF Search view with input and results table."""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Input, Static


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
        with Horizontal():
            yield Input(placeholder="Enter ticker, fund name, or issuer...", id="search-input")
            yield Button("Watch", id="search-watch", variant="warning")
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

        from etfray.data.edgar_service import search_etf

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-watch":
            table = self.query_one("#search-results", DataTable)
            if table.cursor_row is not None and table.row_count > 0:
                ticker = str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
                if ticker and ticker != "—":
                    from etfray.db.database import add_to_watchlist
                    add_to_watchlist("default", ticker)
                    self.app.notify(f"{ticker} added to watchlist")
