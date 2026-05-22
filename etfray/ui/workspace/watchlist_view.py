"""Watchlist Dashboard - track ETFs with concentration, sector, and overlap metrics."""

from __future__ import annotations

import time

import pandas as pd
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Select, Static

WATCHLIST_NAME = "default"
_DOUBLE_CLICK_SECONDS = 0.45

_VERDICT_SHORT = {
    "Broadly diversified": "Broad",
    "Moderately concentrated": "Moderate",
    "Highly concentrated": "High conc.",
}


class WatchlistView(VerticalScroll):
    DEFAULT_CSS = """
    WatchlistView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    WatchlistView #wl-title {
        margin-bottom: 1;
    }
    WatchlistView #wl-add-panel {
        height: 3;
        width: 100%;
        margin-bottom: 1;
    }
    WatchlistView #wl-search-input {
        width: 24;
        margin-right: 1;
    }
    WatchlistView #wl-filter-issuer {
        width: 18;
        margin-right: 1;
    }
    WatchlistView #wl-table-toolbar Button,
    WatchlistView #wl-add-panel Button {
        min-width: 10;
        max-width: 12;
        height: 3;
        margin: 0 0 0 1;
    }
    WatchlistView #wl-search-results {
        height: 8;
        min-height: 8;
        margin-bottom: 1;
    }
    WatchlistView #wl-search-status {
        height: 1;
        margin-bottom: 1;
        color: $text-muted;
    }
    WatchlistView #wl-table-toolbar {
        height: 3;
        width: 100%;
        margin-bottom: 1;
    }
    WatchlistView #wl-filter {
        width: 18;
        margin-right: 1;
    }
    WatchlistView #wl-table {
        height: 1fr;
        min-height: 10;
    }
    """

    BINDINGS = [
        Binding("a", "focus_search", "Add search", show=False),
        Binding("enter", "open_selected", "Open ETF", show=False),
        Binding("delete", "remove_selected", "Remove", show=False),
        Binding("backspace", "remove_selected", "Remove", show=False),
        Binding("ctrl+z", "undo_remove", "Undo", show=False),
    ]

    _rows_data: list[dict] = []
    _last_search_results: list = []
    _last_removed: list[str] = []
    _add_panel_visible: bool = False
    _last_table_click: tuple[str, float] | None = None

    def compose(self) -> ComposeResult:
        yield Static("[bold]Watchlist[/bold]", id="wl-title")
        with Vertical(id="wl-add-section"):
            with Horizontal(id="wl-add-panel"):
                yield Input(
                    placeholder="Search ticker, fund, issuer...",
                    id="wl-search-input",
                )
                yield Select(
                    [("All", "All")],
                    prompt="Issuer: All",
                    id="wl-filter-issuer",
                    allow_blank=False,
                    value="All",
                )
                yield Button("Search", id="wl-search-btn")
                yield Button("Add", id="wl-add-btn")
            yield DataTable(id="wl-search-results")
            yield Static("", id="wl-search-status")
        with Horizontal(id="wl-table-toolbar"):
            yield Button("Add ticker", id="wl-toggle-add")
            yield Input(placeholder="Filter watchlist...", id="wl-filter")
            yield Button("Remove", id="wl-remove")
            yield Button("Refresh", id="wl-refresh")
            yield Button("Export", id="wl-export")
        yield DataTable(id="wl-table")

    def on_mount(self) -> None:
        from etfray.db.database import get_cached_issuers

        search_table = self.query_one("#wl-search-results", DataTable)
        search_table.add_columns("Ticker", "Fund Name", "Issuer", "Status")
        search_table.cursor_type = "row"

        table = self.query_one("#wl-table", DataTable)
        table.add_column("Ticker", width=6)
        table.add_column("Fund Name", width=22)
        table.add_column("Holdings", width=8)
        table.add_column("Top Holding", width=14)
        table.add_column("Top-10 Wt", width=9)
        table.add_column("Eff N", width=5)
        table.add_column("Verdict", width=10)
        table.add_column("Top Sectors", width=24)
        table.add_column("Overlap", width=7)
        table.add_column("Fresh", width=6)
        table.cursor_type = "row"

        issuers = get_cached_issuers()
        issuer_select = self.query_one("#wl-filter-issuer", Select)
        options = [("All", "All")] + [(issuer, issuer) for issuer in issuers]
        issuer_select.set_options(options)
        issuer_select.value = "All"

        self._toggle_add_panel(show=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "wl-search-input" and event.value.strip():
            self._do_search(event.value.strip())

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "wl-filter":
            self._render_table()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "wl-filter-issuer":
            self._render_search_results()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wl-toggle-add":
            self._toggle_add_panel()
        elif event.button.id == "wl-search-btn":
            query = self.query_one("#wl-search-input", Input).value.strip()
            if query:
                self._do_search(query)
        elif event.button.id == "wl-add-btn":
            self._add_selected_search_result()
        elif event.button.id == "wl-remove":
            self._remove_selected()
        elif event.button.id == "wl-refresh":
            self.load_data()
        elif event.button.id == "wl-export":
            self._export()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not event.row_key:
            return
        ticker = str(event.row_key.value)
        if event.control.id == "wl-search-results":
            if ticker not in ("—", "none"):
                self._add_ticker(ticker)
        elif event.control.id == "wl-table":
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

    def _toggle_add_panel(self, show: bool | None = None) -> None:
        if show is None:
            show = not self._add_panel_visible
        self._add_panel_visible = show
        self.query_one("#wl-add-section").display = show
        self.query_one("#wl-toggle-add", Button).label = "Hide add" if show else "Add ticker"

    def action_focus_search(self) -> None:
        if not self._add_panel_visible:
            self._toggle_add_panel(show=True)
        self.query_one("#wl-search-input", Input).focus()

    def action_open_selected(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            ticker = str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
            self.app.navigate_to_etf(ticker)

    def action_remove_selected(self) -> None:
        self._remove_selected()

    def action_undo_remove(self) -> None:
        self._undo_remove()

    def _do_search(self, query: str) -> None:
        self.loading = True
        self.run_worker(self._search_worker(query), name="wl-search", exclusive=True)

    async def _search_worker(self, query: str) -> None:
        from asyncio import to_thread

        from etfray.data.edgar_service import search_etf

        status = self.query_one("#wl-search-status", Static)
        self._last_search_results = await to_thread(search_etf, query)
        self._render_search_results()

        count = self.query_one("#wl-search-results", DataTable).row_count
        if self._last_search_results:
            status.update(
                f"Found {len(self._last_search_results)} result"
                f"{'s' if len(self._last_search_results) != 1 else ''}"
                f" ({count} shown after filters)"
            )
        else:
            status.update("No results found")

        self.loading = False

    def _render_search_results(self) -> None:
        from etfray.db.database import is_in_watchlist

        table = self.query_one("#wl-search-results", DataTable)
        issuer_select = self.query_one("#wl-filter-issuer", Select)
        selected_issuer = issuer_select.value

        table.clear()
        shown = 0
        for result in self._last_search_results:
            if selected_issuer and selected_issuer not in (Select.BLANK, "All"):
                if result.issuer != selected_issuer:
                    continue
            in_list = is_in_watchlist(WATCHLIST_NAME, result.ticker)
            status = "In list" if in_list else "New"
            table.add_row(
                result.ticker,
                result.fund_name[:40],
                result.issuer[:20],
                status,
                key=result.ticker,
            )
            shown += 1

        if not shown:
            if self._last_search_results:
                table.add_row("—", "No matches with current filters", "", "", key="none")

    def _add_selected_search_result(self) -> None:
        table = self.query_one("#wl-search-results", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            self.app.notify("Select a search result to add", severity="warning")
            return
        ticker = str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
        self._add_ticker(ticker)

    def _add_ticker(self, ticker: str) -> None:
        from etfray.db.database import add_to_watchlist

        if not ticker or ticker in ("—", "none"):
            return
        if add_to_watchlist(WATCHLIST_NAME, ticker):
            self.app.notify(f"{ticker} added to watchlist")
            self.load_data()
            self._render_search_results()
        else:
            self.app.notify(f"{ticker} already in watchlist", severity="warning")

    def _remove_selected(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            ticker = str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
            self._remove_tickers([ticker])

    def _remove_tickers(self, tickers: list[str]) -> None:
        from etfray.db.database import is_in_watchlist, remove_from_watchlist

        removed: list[str] = []
        not_found: list[str] = []
        for ticker in tickers:
            if is_in_watchlist(WATCHLIST_NAME, ticker):
                remove_from_watchlist(WATCHLIST_NAME, ticker)
                removed.append(ticker)
            else:
                not_found.append(ticker)

        if removed:
            self._last_removed = removed
            self.app.notify(f"Removed {', '.join(removed)} — press Ctrl+Z to undo")
            self.load_data()
            self._render_search_results()

        if not_found and not removed:
            self.app.notify(f"{', '.join(not_found)} not in watchlist", severity="warning")
        elif not_found:
            self.app.notify(f"Not in watchlist: {', '.join(not_found)}", severity="warning")

    def _undo_remove(self) -> None:
        from etfray.db.database import add_to_watchlist

        if not self._last_removed:
            self.app.notify("Nothing to undo", severity="warning")
            return

        for ticker in self._last_removed:
            add_to_watchlist(WATCHLIST_NAME, ticker)
        restored = self._last_removed
        self._last_removed = []
        self.app.notify(f"Restored {', '.join(restored)}")
        self.load_data()
        self._render_search_results()

    def load_data(self) -> None:
        self.loading = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from etfray.db.database import get_watchlist

        self._rows_data = []

        tickers = get_watchlist(WATCHLIST_NAME)
        if not tickers:
            self._render_table()
            self.loading = False
            return

        preference = getattr(self.app, "_data_source", "auto")
        portfolio_df = await self._get_portfolio_df(preference)

        for ticker in tickers:
            row = await self._build_row(ticker, preference, portfolio_df)
            self._rows_data.append(row)

        self._render_table()
        self.loading = False

    def _render_table(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        filter_text = self.query_one("#wl-filter", Input).value.strip().lower()
        table.clear()

        for row in self._rows_data:
            if filter_text:
                haystack = f"{row['ticker']} {row['fund_name']}".lower()
                if filter_text not in haystack:
                    continue
            table.add_row(
                row["ticker"],
                row["fund_name"],
                row["holdings"],
                row["top_holding"],
                row["top10"],
                row["eff_n"],
                row["verdict"],
                row["sectors"],
                row["overlap"],
                row["fresh"],
                key=row["ticker"],
            )

    async def _build_row(self, ticker: str, preference: str, portfolio_df) -> dict:
        from datetime import date, datetime

        from etfray.db.database import get_cached_etf, get_cached_holdings
        from etfray.domain.etf_analytics import (
            calculate_concentration,
            calculate_exposure,
            calculate_weight_overlap,
        )

        row: dict = {
            "ticker": ticker,
            "fund_name": "",
            "holdings": "—",
            "top_holding": "—",
            "top10": "—",
            "eff_n": "—",
            "verdict": "—",
            "sectors": "—",
            "overlap": "—",
            "fresh": "—",
        }

        cached_etf = get_cached_etf(ticker)
        if cached_etf:
            row["fund_name"] = cached_etf.fund_name[:25]

        cached = get_cached_holdings(ticker)
        if not cached or not cached.get("holdings_json"):
            return row

        import io

        try:
            df = pd.read_json(io.StringIO(cached["holdings_json"]))
        except Exception:
            return row

        if df.empty:
            return row

        conc = calculate_concentration(df)
        row["holdings"] = f"{conc.num_holdings:,}"
        row["top_holding"] = conc.largest_holding[:15]
        row["top10"] = f"{conc.top10_weight:.1f}%"
        row["eff_n"] = f"{conc.effective_n:.0f}"
        row["verdict"] = _VERDICT_SHORT.get(conc.verdict, conc.verdict[:10])

        if cached.get("as_of_date"):
            try:
                as_of = datetime.fromisoformat(cached["as_of_date"]).date()
                days = (date.today() - as_of).days
                if days < 60:
                    row["fresh"] = f"{days}d"
                elif days < 150:
                    row["fresh"] = f"~{days}d"
                else:
                    row["fresh"] = f"!{days}d"
            except (ValueError, TypeError):
                pass

        if "ticker" in df.columns:
            try:
                from etfray.db.database import get_cached_sectors_bulk

                ticker_list = df["ticker"].dropna().astype(str).str.upper().str.strip().tolist()
                ticker_list = [t for t in ticker_list if t]
                sector_map = get_cached_sectors_bulk(ticker_list)
                if sector_map:
                    df_copy = df.copy()
                    df_copy["sector"] = df_copy["ticker"].apply(
                        lambda t: sector_map.get(str(t).upper().strip(), "Unclassified")
                        if pd.notna(t) and str(t).strip()
                        else "Unclassified"
                    )
                    exposure = calculate_exposure(df_copy, "sector")
                    top3 = [f"{e.category[:4]} {e.weight:.0f}%" for e in exposure[:3]]
                    row["sectors"] = " | ".join(top3)
            except Exception:
                pass

        if portfolio_df is not None and not portfolio_df.empty:
            try:
                overlap = calculate_weight_overlap(portfolio_df, df)
                row["overlap"] = f"{overlap:.1f}%"
            except Exception:
                pass

        return row

    async def _get_portfolio_df(self, preference: str):
        """Build a combined holdings DataFrame from IBKR positions using cached data only."""
        import io

        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.db.database import get_cached_holdings

        svc = get_ibkr_service()
        if not svc.is_connected or not svc.positions:
            return None

        total_value = sum(abs(p.market_value) for p in svc.positions)
        if total_value == 0:
            return None

        frames = []
        for p in sorted(svc.positions, key=lambda x: abs(x.market_value), reverse=True)[:5]:
            weight = abs(p.market_value) / total_value
            cached = get_cached_holdings(p.symbol)
            if not cached or not cached.get("holdings_json"):
                continue
            try:
                df = pd.read_json(io.StringIO(cached["holdings_json"]))
                if not df.empty and "ticker" in df.columns and "pct_value" in df.columns:
                    df_copy = df[["ticker", "pct_value"]].copy()
                    df_copy["pct_value"] = df_copy["pct_value"] * weight
                    frames.append(df_copy)
            except Exception:
                continue

        if not frames:
            return None

        combined = pd.concat(frames, ignore_index=True)
        combined = combined.groupby("ticker", as_index=False)["pct_value"].sum()
        return combined

    def _export(self) -> None:
        if not self._rows_data:
            self.app.notify("No data to export", severity="warning")
            return
        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings

        df = pd.DataFrame(self._rows_data)
        path = export_dataframe_csv(df, "watchlist", load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
