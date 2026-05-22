"""ETF Search view with input and results table."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static

_DOUBLE_CLICK_SECONDS = 0.45


class SearchView(Vertical):
    """Search page — Vertical + grid (not VerticalScroll) so controls stay top and table fills below."""

    DEFAULT_CSS = """
    SearchView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
        layout: grid;
        grid-size: 1 2;
        grid-rows: auto 1fr;
        grid-gutter: 0 1;
    }
    SearchView #search-toolbar {
        height: auto;
        width: 100%;
        row-span: 1;
        layout: vertical;
    }
    SearchView #search-toolbar Horizontal {
        height: auto;
        min-height: 3;
        width: 100%;
    }
    SearchView #search-input {
        height: 3;
        min-height: 3;
        width: 1fr;
        margin-bottom: 1;
    }
    SearchView #search-watch {
        height: 3;
        min-height: 3;
        margin-left: 1;
    }
    SearchView #search-status {
        height: auto;
        min-height: 1;
    }
    SearchView #search-results {
        width: 100%;
        height: 100%;
        min-height: 0;
        row-span: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "open_selected", "Open ETF", show=False),
    ]

    _last_table_click: tuple[str, float] | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="search-toolbar"):
            yield Static("Search ETF / Fund / Issuer")
            with Horizontal():
                yield Input(placeholder="Enter ticker, fund name, or issuer...", id="search-input")
                yield Button("Watch", id="search-watch")
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
        self.loading = True
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

        self.loading = False
        self._update_watch_button()

    def _get_selected_ticker(self) -> str | None:
        table = self.query_one("#search-results", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            ticker = str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
            if ticker and ticker != "—":
                return ticker
        return None

    def _update_watch_button(self) -> None:
        from etfray.db.database import is_in_watchlist

        button = self.query_one("#search-watch", Button)
        ticker = self._get_selected_ticker()
        if ticker and is_in_watchlist("default", ticker):
            button.label = "Unwatch"
        else:
            button.label = "Watch"

    def action_open_selected(self) -> None:
        ticker = self._get_selected_ticker()
        if ticker:
            self.app.navigate_to_etf(ticker)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not event.row_key:
            return
        ticker = str(event.row_key.value)
        if ticker == "—":
            return
        self._update_watch_button()
        now = time.monotonic()
        if (
            self._last_table_click
            and self._last_table_click[0] == ticker
            and now - self._last_table_click[1] < _DOUBLE_CLICK_SECONDS
        ):
            self._last_table_click = None
            self.app.navigate_to_etf(ticker)
        else:
            self._last_table_click = (ticker, now)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-watch":
            ticker = self._get_selected_ticker()
            if not ticker:
                self.app.notify("Select a search result first", severity="warning")
                return

            from etfray.db.database import add_to_watchlist, is_in_watchlist, remove_from_watchlist

            if is_in_watchlist("default", ticker):
                remove_from_watchlist("default", ticker)
                self.app.notify(f"{ticker} removed from watchlist")
            elif add_to_watchlist("default", ticker):
                self.app.notify(f"{ticker} added to watchlist")
            else:
                self.app.notify(f"{ticker} already in watchlist", severity="warning")

            self._update_watch_button()
