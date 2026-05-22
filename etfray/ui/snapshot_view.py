"""Snapshot Home View — startup landing screen for ETFray."""

from __future__ import annotations

import json
import threading
import time
from datetime import date, datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Static

BENCHMARK_TICKERS = ["SPY", "QQQ", "AGG", "GLD"]
_DOUBLE_CLICK_SECONDS = 0.45


class SnapshotView(VerticalScroll):
    DEFAULT_CSS = """
    SnapshotView {
        display: none;
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    SnapshotView #snap-benchmarks {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        background: $surface;
        border: solid $primary-background;
    }
    SnapshotView #snap-bench-text {
        width: 1fr;
    }
    SnapshotView #snap-bench-refresh {
        min-width: 11;
        max-width: 11;
        height: 1;
        margin-left: 1;
    }
    SnapshotView #snap-middle {
        height: auto;
        margin-bottom: 1;
    }
    SnapshotView #snap-watchlist-pane {
        width: 1fr;
        height: auto;
        min-height: 10;
        border: solid $primary-background;
        padding: 1;
    }
    SnapshotView #snap-watchlist-header {
        height: 1;
        margin-bottom: 1;
    }
    SnapshotView #snap-watchlist-table {
        height: auto;
        min-height: 6;
        max-height: 14;
    }
    SnapshotView #snap-watchlist-footer {
        height: 3;
        margin-top: 1;
    }
    SnapshotView #snap-watchlist-footer Button {
        min-width: 18;
    }
    SnapshotView #snap-recent {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
    }
    SnapshotView #snap-keys {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    """

    _last_watchlist_click: tuple[str, float] | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="snap-benchmarks"):
            yield Static("Benchmarks: loading…", id="snap-bench-text")
            yield Button("Refresh", id="snap-bench-refresh")

        with Horizontal(id="snap-middle"):
            with Vertical(id="snap-watchlist-pane"):
                yield Static("[bold]── Watchlist ──[/bold]", id="snap-watchlist-header")
                yield DataTable(id="snap-watchlist-table")
                with Horizontal(id="snap-watchlist-footer"):
                    yield Button("Go to Watchlist →", id="snap-go-watchlist")

        yield Static("── Recent / Quick Jump ──\n", id="snap-recent")
        yield Static(
            "── Quick Keys ──\n"
            "  /  Search       p  Portfolio\n"
            "  t  Seasonals    h  Holdings\n"
            "  x  Exposure     c  Concentr.\n"
            "  m  Margin       r  Risk\n"
            "  d  Documents    Esc  Home\n"
            "  w  Watch        s  Source\n"
            " ^I  IBKR          q  Quit",
            id="snap-keys",
        )

    def on_mount(self) -> None:
        table = self.query_one("#snap-watchlist-table", DataTable)
        table.add_column("Ticker", width=7)
        table.add_column("Fund Name", width=22)
        table.add_column("YTD", width=8)
        table.add_column("Top-10 Wt", width=10)
        table.add_column("Eff N", width=6)
        table.add_column("Fresh", width=6)
        table.cursor_type = "row"
        # display starts as none via CSS — first paint never shows this widget.
        # ContentSwitcher restores display=True when current="home" is set.

    # ── Public refresh entry point ─────────────────────────────────────────

    def refresh_all(self) -> None:
        """Re-render all panels. Safe to call from navigate_to() and _on_splash_dismissed()."""
        self._render_benchmarks()
        self._load_watchlist()
        self._render_recent()

    # ── Benchmark Strip ────────────────────────────────────────────────────

    def _render_benchmarks(self) -> None:
        from etfray.db.database import get_cached_etf_profile

        parts: list[str] = []
        for ticker in BENCHMARK_TICKERS:
            row = get_cached_etf_profile(ticker)
            if row:
                try:
                    profile = json.loads(row["profile_json"])
                    ytd = profile.get("ytd_return")
                    if ytd is not None:
                        sign = "+" if ytd >= 0 else ""
                        color = "green" if ytd >= 0 else "red"
                        parts.append(f"{ticker} [{color}]{sign}{ytd * 100:.1f}%[/{color}] YTD")
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

        if parts:
            text = "Benchmarks:  " + "   ".join(parts) + "  [dim](cached)[/dim]"
        else:
            text = "Benchmarks: — [dim](open any ETF to populate cache)[/dim]"

        self.query_one("#snap-bench-text", Static).update(text)

    def _fetch_benchmarks_in_thread(self) -> None:
        """Fetch each benchmark profile from Yahoo (blocking). Call from a worker thread."""
        from etfray.data.market_data_service import get_etf_profile

        for ticker in BENCHMARK_TICKERS:
            try:
                get_etf_profile(ticker)
            except Exception:
                pass
        self.app.call_from_thread(self._render_benchmarks)

    # ── Watchlist Summary (async worker) ──────────────────────────────────

    def _load_watchlist(self) -> None:
        self.run_worker(self._watchlist_worker(), exclusive=True, name="snap-watchlist")

    async def _watchlist_worker(self) -> None:
        from asyncio import to_thread

        import io

        import pandas as pd

        from etfray.db.database import (
            get_cached_etf,
            get_cached_etf_profile,
            get_cached_holdings,
            get_watchlist,
        )
        from etfray.domain.etf_analytics import calculate_concentration

        tickers = get_watchlist("default")
        table = self.query_one("#snap-watchlist-table", DataTable)
        table.clear()

        if not tickers:
            table.add_row("—", "No tickers in watchlist — open Search and press W", "—", "—", "—", "—", key="none")
            return

        for ticker in tickers:
            row_data: dict[str, str] = {
                "fund_name": "—",
                "ytd": "—",
                "top10": "—",
                "eff_n": "—",
                "fresh": "—",
            }

            cached_etf = await to_thread(get_cached_etf, ticker)
            if cached_etf:
                row_data["fund_name"] = cached_etf.fund_name[:25]

            profile_row = await to_thread(get_cached_etf_profile, ticker)
            if profile_row:
                try:
                    profile = json.loads(profile_row["profile_json"])
                    ytd = profile.get("ytd_return")
                    if ytd is not None:
                        sign = "+" if ytd >= 0 else ""
                        color = "green" if ytd >= 0 else "red"
                        row_data["ytd"] = f"[{color}]{sign}{ytd * 100:.1f}%[/{color}]"
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

            cached_h = await to_thread(get_cached_holdings, ticker)
            if cached_h and cached_h.get("holdings_json"):
                try:
                    df = pd.read_json(io.StringIO(cached_h["holdings_json"]))
                    if not df.empty:
                        conc = calculate_concentration(df)
                        row_data["top10"] = f"{conc.top10_weight:.1f}%"
                        row_data["eff_n"] = f"{conc.effective_n:.0f}"
                except Exception:
                    pass

                if cached_h.get("as_of_date"):
                    try:
                        as_of = datetime.fromisoformat(cached_h["as_of_date"]).date()
                        days = (date.today() - as_of).days
                        if days < 60:
                            row_data["fresh"] = f"{days}d"
                        elif days < 150:
                            row_data["fresh"] = f"~{days}d"
                        else:
                            row_data["fresh"] = f"!{days}d"
                    except (ValueError, TypeError):
                        pass

            table.add_row(
                ticker,
                row_data["fund_name"],
                row_data["ytd"],
                row_data["top10"],
                row_data["eff_n"],
                row_data["fresh"],
                key=ticker,
            )

    # ── Recent ETFs ────────────────────────────────────────────────────────

    def _render_recent(self) -> None:
        from etfray.db.database import get_note

        note = get_note("system", "recent_etfs")
        tickers: list[str] = []
        if note:
            try:
                tickers = json.loads(note.content)
            except (json.JSONDecodeError, AttributeError):
                pass

        if tickers:
            pills = "  ".join(f"[bold]{t}[/bold]" for t in tickers)
            text = f"── Recent / Quick Jump ──\n  Last viewed:  {pills}   [Search →]"
        else:
            text = (
                "── Recent / Quick Jump ──\n"
                "  [dim]No recent ETFs yet — search and open one to populate.[/dim]   [Search →]"
            )

        self.query_one("#snap-recent", Static).update(text)

    # ── Event handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "snap-bench-refresh":
            threading.Thread(target=self._fetch_benchmarks_in_thread, daemon=True).start()
            self.app.notify("Refreshing benchmarks…", timeout=8)
        elif bid == "snap-go-watchlist":
            self.app.navigate_to("workspace-watchlist")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.control.id != "snap-watchlist-table" or not event.row_key:
            return
        ticker = str(event.row_key.value)
        if ticker in ("—", "none"):
            return
        now = time.monotonic()
        if (
            self._last_watchlist_click
            and self._last_watchlist_click[0] == ticker
            and now - self._last_watchlist_click[1] < _DOUBLE_CLICK_SECONDS
        ):
            self._last_watchlist_click = None
            self.app.navigate_to_etf(ticker)
        else:
            self._last_watchlist_click = (ticker, now)
