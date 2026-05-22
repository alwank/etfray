"""ETF Search / Discovery view — browse by asset class, category, and geography,
or type a ticker/name and press Enter to search EDGAR directly.
"""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Input, Label, ListItem, ListView, Static

_DOUBLE_CLICK_SECONDS = 0.45

_ALL_LABEL = "All"

_ASSET_CLASSES = [
    "Equity",
    "Fixed Income",
    "Real Estate",
    "Commodity",
    "Multi-Asset",
]

_CATEGORIES = [
    "Broad Market",
    "Sector / Thematic",
    "Factor / Smart Beta",
    "Fixed Income",
    "Real Estate",
    "Commodity",
    "Multi-Asset",
    "Leveraged / Inverse",
    "Currency",
]

_GEOGRAPHIES = [
    "US",
    "International",
    "Emerging Markets",
    "Single Country",
]


class _DimSection(Vertical):
    """A titled list of filter options for one dimension."""

    DEFAULT_CSS = """
    _DimSection {
        height: auto;
        margin-bottom: 1;
    }
    _DimSection .dim-title {
        text-style: bold;
        color: $text-muted;
        padding: 0 1;
        height: 1;
    }
    _DimSection ListView {
        height: auto;
        background: transparent;
        border: none;
        padding: 0;
    }
    _DimSection ListItem {
        padding: 0 1;
        height: 1;
    }
    _DimSection ListItem:hover {
        background: $surface-lighten-1;
    }
    _DimSection ListItem.-active {
        background: $accent;
        color: $text;
        text-style: bold;
    }
    _DimSection ListItem Label {
        width: 100%;
    }
    """

    def __init__(self, title: str, items: list[str], dim_id: str) -> None:
        super().__init__()
        self._title = title
        self._items = items
        self._dim_id = dim_id

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="dim-title")
        lv = ListView(id=f"lv-{self._dim_id}")
        # "All" entry first
        lv._pending_items = [_ALL_LABEL] + self._items
        yield lv

    def on_mount(self) -> None:
        lv = self.query_one(ListView)
        for label in [_ALL_LABEL] + self._items:
            lv.append(ListItem(Label(label), name=label))
        # Highlight "All" by default
        if lv.children:
            lv.index = 0


class DiscoveryView(Horizontal):
    """Home / discovery page — two-column layout with dimension browser and ETF table."""

    DEFAULT_CSS = """
    DiscoveryView {
        height: 1fr;
        min-height: 1fr;
    }

    /* Left panel */
    DiscoveryView #discovery-left {
        width: 30;
        min-width: 30;
        border-right: solid $primary-background;
        padding: 1 0;
        overflow-y: auto;
        background: $surface;
    }
    DiscoveryView #discovery-left-title {
        text-style: bold;
        padding: 0 1 1 1;
        color: $text;
    }

    /* Right panel */
    DiscoveryView #discovery-right {
        width: 1fr;
        padding: 1 2;
        layout: grid;
        grid-size: 1 3;
        grid-rows: auto auto 1fr;
    }
    DiscoveryView #discovery-header {
        height: auto;
        padding-bottom: 0;
    }
    DiscoveryView #discovery-filter-row {
        height: auto;
        min-height: 3;
        layout: horizontal;
    }
    DiscoveryView #discovery-filter {
        width: 1fr;
        height: 3;
    }
    DiscoveryView #discovery-watch {
        height: 3;
        margin-left: 1;
    }
    DiscoveryView #discovery-count {
        width: auto;
        height: 3;
        content-align: right middle;
        padding: 0 1;
        color: $text-muted;
    }
    DiscoveryView #discovery-table {
        height: 1fr;
        min-height: 0;
    }
    """

    BINDINGS = [
        Binding("enter", "open_selected", "Open ETF", show=False),
    ]

    # Currently selected dimension filters
    _filter_asset: reactive[str] = reactive(_ALL_LABEL)
    _filter_category: reactive[str] = reactive(_ALL_LABEL)
    _filter_geography: reactive[str] = reactive(_ALL_LABEL)
    _filter_text: reactive[str] = reactive("")

    _last_table_click: tuple[str, float] | None = None
    _universe: list = []  # list[ETFUniverseEntry]

    def compose(self) -> ComposeResult:
        with Vertical(id="discovery-left"):
            yield Static("Browse", id="discovery-left-title")
            yield _DimSection("Asset Class", _ASSET_CLASSES, "asset")
            yield _DimSection("Category", _CATEGORIES, "cat")
            yield _DimSection("Geography", _GEOGRAPHIES, "geo")

        with Vertical(id="discovery-right"):
            yield Static("Search / Discover ETFs", id="discovery-header")
            with Horizontal(id="discovery-filter-row"):
                yield Input(placeholder="Filter by name, ticker, or issuer... (Enter to search EDGAR)", id="discovery-filter")
                yield Button("Watch", id="discovery-watch")
                yield Static("Loading...", id="discovery-count")
            yield DataTable(id="discovery-table")

    def on_mount(self) -> None:
        table = self.query_one("#discovery-table", DataTable)
        table.add_columns("Ticker", "Fund Name", "Issuer", "Asset Class", "Geography")
        table.cursor_type = "row"
        # Load universe in background
        self.run_worker(self._load_universe(), name="discovery-load", exclusive=True)

    # ------------------------------------------------------------------ workers

    async def _load_universe(self) -> None:
        from asyncio import to_thread

        from etfray.data.edgar_service import get_etf_universe

        self.loading = True
        universe = await to_thread(get_etf_universe)
        self._universe = universe
        self.loading = False
        self._repopulate_table()

    # ------------------------------------------------------------------ reactive watches

    def watch__filter_asset(self, _value: str) -> None:
        self._repopulate_table()

    def watch__filter_category(self, _value: str) -> None:
        self._repopulate_table()

    def watch__filter_geography(self, _value: str) -> None:
        self._repopulate_table()

    def watch__filter_text(self, _value: str) -> None:
        self._repopulate_table()

    # ------------------------------------------------------------------ table population

    def _repopulate_table(self) -> None:
        if not self._universe:
            return

        table = self.query_one("#discovery-table", DataTable)
        table.clear()

        text = self._filter_text.lower()
        rows_added = 0

        for entry in self._universe:
            if self._filter_asset != _ALL_LABEL and entry.asset_class != self._filter_asset:
                continue
            if self._filter_category != _ALL_LABEL and entry.category != self._filter_category:
                continue
            if self._filter_geography != _ALL_LABEL and entry.geography != self._filter_geography:
                continue
            if text and not (
                text in entry.ticker.lower()
                or text in entry.fund_name.lower()
                or text in entry.issuer.lower()
            ):
                continue

            table.add_row(
                entry.ticker,
                entry.fund_name[:45],
                entry.issuer[:30],
                entry.asset_class,
                entry.geography,
                key=entry.ticker,
            )
            rows_added += 1

        count_widget = self.query_one("#discovery-count", Static)
        count_widget.update(f"{rows_added:,} ETFs")

    # ------------------------------------------------------------------ dimension selection

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.name is None:
            return
        selected = event.item.name
        lv_id = event.list_view.id

        if lv_id == "lv-asset":
            self._filter_asset = selected
        elif lv_id == "lv-cat":
            self._filter_category = selected
        elif lv_id == "lv-geo":
            self._filter_geography = selected

    # ------------------------------------------------------------------ text filter

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "discovery-filter":
            self._filter_text = event.value.strip()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """On Enter, run an EDGAR search for tickers not found in the local universe."""
        if event.input.id != "discovery-filter":
            return
        query = event.value.strip()
        if not query:
            return

        table = self.query_one("#discovery-table", DataTable)
        # If the local filter already returned results, just open the top one
        if table.row_count > 0:
            self.action_open_selected()
            return

        # No local results — fall through to EDGAR search
        self.run_worker(self._edgar_search_worker(query), name="edgar-search", exclusive=True)

    async def _edgar_search_worker(self, query: str) -> None:
        from asyncio import to_thread

        from etfray.data.edgar_service import search_etf

        self.loading = True
        results = await to_thread(search_etf, query)
        self.loading = False

        table = self.query_one("#discovery-table", DataTable)
        count = self.query_one("#discovery-count", Static)
        table.clear()

        for r in results:
            table.add_row(r.ticker, r.fund_name[:45], r.issuer[:30], "—", "—", key=r.ticker)

        if results:
            count.update(f"{len(results)} result{'s' if len(results) != 1 else ''} (EDGAR)")
            self._update_watch_button()
        else:
            table.add_row("—", "No results found", "", "", "")
            count.update("")

    # ------------------------------------------------------------------ watch button

    def _update_watch_button(self) -> None:
        from etfray.db.database import is_in_watchlist

        button = self.query_one("#discovery-watch", Button)
        ticker = self._get_selected_ticker()
        if ticker and is_in_watchlist("default", ticker):
            button.label = "Unwatch"
        else:
            button.label = "Watch"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "discovery-watch":
            return
        ticker = self._get_selected_ticker()
        if not ticker or ticker == "—":
            self.app.notify("Select an ETF first", severity="warning")
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

    # ------------------------------------------------------------------ table interaction

    def _get_selected_ticker(self) -> str | None:
        table = self.query_one("#discovery-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            ticker = str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
            if ticker:
                return ticker
        return None

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