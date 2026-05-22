"""ETF Search / Discovery view — filter by asset class, category, and geography,
or type a ticker/name and press Enter to search EDGAR directly.
"""

from __future__ import annotations

import time

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Input, Label, Static

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


def _pill_id(dim: str, value: str) -> str:
    safe = value.replace(" ", "_").replace("/", "_")
    return f"pill-{dim}-{safe}"


class DiscoveryView(Vertical):
    """ETF search and discovery page — horizontal filter pills above a full-width table."""

    DEFAULT_CSS = """
    DiscoveryView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }

    /* Search row */
    DiscoveryView #discovery-search-row {
        height: auto;
        min-height: 3;
        margin-bottom: 0;
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

    /* Filter pill rows */
    DiscoveryView .filter-row {
        height: 1;
        padding: 0;
        margin-top: 1;
    }
    DiscoveryView .filter-label {
        width: auto;
        height: 1;
        padding: 0 1 0 0;
        color: $text-muted;
        content-align: left middle;
    }

    /* Pills use Static — unaffected by global Button CSS */
    DiscoveryView .filter-pill {
        height: 1;
        width: auto;
        padding: 0 1;
        margin: 0 0 0 0;
        background: transparent;
        color: $text-muted;
    }
    DiscoveryView .filter-pill:hover {
        background: $surface-lighten-1;
        color: $text;
    }
    DiscoveryView .filter-pill.-on {
        background: steelblue;
        color: white;
        text-style: bold;
    }

    /* Table */
    DiscoveryView #discovery-table {
        height: 1fr;
        min-height: 0;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "open_selected", "Open ETF", show=False),
    ]

    _filter_asset: reactive[str] = reactive(_ALL_LABEL)
    _filter_category: reactive[str] = reactive(_ALL_LABEL)
    _filter_geography: reactive[str] = reactive(_ALL_LABEL)
    _filter_text: reactive[str] = reactive("")

    _last_table_click: tuple[str, float] | None = None
    _universe: list = []  # list[ETFUniverseEntry]

    def compose(self) -> ComposeResult:
        # Row 1: search input + watch button + result count
        with Horizontal(id="discovery-search-row"):
            yield Input(
                placeholder="Filter by name, ticker, or issuer... (Enter to search EDGAR)",
                id="discovery-filter",
            )
            yield Button("Watch", id="discovery-watch")
            yield Static("Loading...", id="discovery-count")

        # Row 2: Asset Class pills (Static widgets — immune to global Button CSS)
        with Horizontal(classes="filter-row", id="discovery-filter-asset"):
            yield Label("Class:", classes="filter-label")
            yield Static(_ALL_LABEL, classes="filter-pill -on", name="asset:All", id=_pill_id("asset", "All"))
            for ac in _ASSET_CLASSES:
                yield Static(ac, classes="filter-pill", name=f"asset:{ac}", id=_pill_id("asset", ac))

        # Row 3: Category pills
        with Horizontal(classes="filter-row", id="discovery-filter-cat"):
            yield Label("Cat:", classes="filter-label")
            yield Static(_ALL_LABEL, classes="filter-pill -on", name="cat:All", id=_pill_id("cat", "All"))
            for cat in _CATEGORIES:
                yield Static(cat, classes="filter-pill", name=f"cat:{cat}", id=_pill_id("cat", cat))

        # Row 4: Geography pills
        with Horizontal(classes="filter-row", id="discovery-filter-geo"):
            yield Label("Geo:", classes="filter-label")
            yield Static(_ALL_LABEL, classes="filter-pill -on", name="geo:All", id=_pill_id("geo", "All"))
            for geo in _GEOGRAPHIES:
                yield Static(geo, classes="filter-pill", name=f"geo:{geo}", id=_pill_id("geo", geo))

        yield DataTable(id="discovery-table")

    def on_mount(self) -> None:
        table = self.query_one("#discovery-table", DataTable)
        table.add_columns("Ticker", "Fund Name", "Issuer", "Category", "Geography")
        table.cursor_type = "row"
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
                entry.fund_name[:55],
                entry.issuer[:30],
                entry.category,
                entry.geography,
                key=entry.ticker,
            )
            rows_added += 1

        self._update_count(rows_added)

    def _update_count(self, n: int) -> None:
        active = [
            f"[{v}]"
            for v in (self._filter_asset, self._filter_category, self._filter_geography)
            if v != _ALL_LABEL
        ]
        suffix = "  " + " ".join(active) if active else ""
        self.query_one("#discovery-count", Static).update(f"{n:,} ETFs{suffix}")

    # ------------------------------------------------------------------ pill filter interaction

    def on_click(self, event: events.Click) -> None:
        """Handle clicks on filter pill Static widgets."""
        widget = event.widget
        name = getattr(widget, "name", "") or ""
        if not name or ":" not in name:
            return

        # Stop the event so it doesn't bubble further
        event.stop()

        dim, value = name.split(":", 1)

        if dim == "asset":
            new_val = _ALL_LABEL if (value != _ALL_LABEL and self._filter_asset == value) else value
            self._set_pill_group("asset", new_val)
            self._filter_asset = new_val
        elif dim == "cat":
            new_val = _ALL_LABEL if (value != _ALL_LABEL and self._filter_category == value) else value
            self._set_pill_group("cat", new_val)
            self._filter_category = new_val
        elif dim == "geo":
            new_val = _ALL_LABEL if (value != _ALL_LABEL and self._filter_geography == value) else value
            self._set_pill_group("geo", new_val)
            self._filter_geography = new_val

    def _set_pill_group(self, dim: str, active_value: str) -> None:
        """Update -on class for all pills in the given dimension group."""
        prefix = f"pill-{dim}-"
        for widget in self.query(Static):
            if widget.id and widget.id.startswith(prefix):
                pill_value = (widget.name or "").split(":", 1)[-1]
                if pill_value == active_value:
                    widget.add_class("-on")
                else:
                    widget.remove_class("-on")

    # ------------------------------------------------------------------ Watch button

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "discovery-watch":
            self._handle_watch()

    # ------------------------------------------------------------------ text filter

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "discovery-filter":
            self._filter_text = event.value.strip()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """On Enter, open the top result or fall back to an EDGAR search."""
        if event.input.id != "discovery-filter":
            return
        query = event.value.strip()
        if not query:
            return

        table = self.query_one("#discovery-table", DataTable)
        if table.row_count > 0:
            self.action_open_selected()
            return

        self.run_worker(self._edgar_search_worker(query), name="edgar-search", exclusive=True)

    async def _edgar_search_worker(self, query: str) -> None:
        from asyncio import to_thread

        from etfray.data.edgar_service import search_etf

        self.loading = True
        results = await to_thread(search_etf, query)
        self.loading = False

        table = self.query_one("#discovery-table", DataTable)
        table.clear()

        for r in results:
            table.add_row(r.ticker, r.fund_name[:55], r.issuer[:30], "—", "—", key=r.ticker)

        count = self.query_one("#discovery-count", Static)
        if results:
            count.update(f"{len(results)} result{'s' if len(results) != 1 else ''} (EDGAR)")
            self._update_watch_button()
        else:
            table.add_row("—", "No results found", "", "", "")
            count.update("")

    # ------------------------------------------------------------------ watch button

    def _handle_watch(self) -> None:
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

    def _update_watch_button(self) -> None:
        from etfray.db.database import is_in_watchlist

        button = self.query_one("#discovery-watch", Button)
        ticker = self._get_selected_ticker()
        if ticker and ticker != "—" and is_in_watchlist("default", ticker):
            button.label = "Unwatch"
        else:
            button.label = "Watch"

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
        if ticker and ticker != "—":
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
