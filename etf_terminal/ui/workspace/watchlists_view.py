"""Watchlists view - track ETFs without owning them."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Input, Button, DataTable
from textual.containers import VerticalScroll

from etf_terminal.db.database import add_to_watchlist, remove_from_watchlist, get_all_watchlists


class WatchlistsView(VerticalScroll):
    DEFAULT_CSS = """
    WatchlistsView {
        padding: 1 2;
    }
    WatchlistsView DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Watchlists[/bold]")
        with Horizontal():
            yield Input(placeholder="Watchlist name", id="wl-name")
            yield Input(placeholder="Ticker", id="wl-ticker")
            yield Button("Add", id="wl-add")
            yield Button("Remove", id="wl-remove")
        yield DataTable(id="wl-table")

    def on_mount(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        table.add_columns("Watchlist", "Ticker")
        table.cursor_type = "row"
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        name = self.query_one("#wl-name", Input).value.strip() or "My ETFs"
        ticker = self.query_one("#wl-ticker", Input).value.strip().upper()
        if not ticker:
            return
        if event.button.id == "wl-add":
            add_to_watchlist(name, ticker)
        elif event.button.id == "wl-remove":
            remove_from_watchlist(name, ticker)
        self._refresh()

    def _refresh(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        table.clear()
        for name, tickers in get_all_watchlists().items():
            for t in tickers:
                table.add_row(name, t, key=f"{name}:{t}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            parts = str(event.row_key.value).split(":")
            if len(parts) == 2:
                self.app.navigate_to_etf(parts[1])
