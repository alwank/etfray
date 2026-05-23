"""Snapshot Home View — startup landing screen for ETFray."""

from __future__ import annotations

import json
import threading
import time

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label, Static

BENCHMARK_TICKERS = ["SPY", "QQQ", "AGG", "GLD"]
_DOUBLE_CLICK_SECONDS = 0.45


class BenchmarkTicker(Widget):
    """Horizontally scrolling marquee for benchmark YTD returns."""

    _text_loop: Text | None = None  # one loop unit as a Rich Text (span-aware)
    _loop_len: int = 0              # visible character length of one loop
    _offset: int = 0
    _paused: bool = False

    _SPEED: int = 1          # visible characters to advance per tick
    _INTERVAL: float = 0.18  # seconds per tick (~5 fps)
    _SEP: str = "     ★     "

    DEFAULT_CSS = """
    BenchmarkTicker {
        height: 1fr;
        content-align: left middle;
    }
    """

    def on_mount(self) -> None:
        self.set_interval(self._INTERVAL, self._tick)

    def set_content(self, markup: str) -> None:
        """Set the marquee text. Accepts Rich markup."""
        self._text_loop = Text.from_markup(markup + self._SEP)
        self._loop_len = len(self._text_loop)
        self._offset = 0
        self.refresh()

    def _tick(self) -> None:
        if not self._loop_len or self._paused:
            return
        self._offset = (self._offset + self._SPEED) % self._loop_len
        self.refresh()

    def on_enter(self) -> None:
        self._paused = True

    def on_leave(self) -> None:
        self._paused = False

    def render(self) -> Text:
        if self._text_loop is None or self._loop_len == 0:
            return Text("Benchmarks: loading…")

        width = self.size.width or 80

        # Repeat the loop unit enough times so we can always slice `width` chars
        # starting from any offset without running out of text.
        reps = width // self._loop_len + 3
        full = Text()
        for _ in range(reps):
            full.append_text(self._text_loop)

        # Rich Text slicing correctly adjusts all style spans — no MarkupError risk.
        return full[self._offset : self._offset + width]


class SnapshotView(VerticalScroll):
    DEFAULT_CSS = """
    SnapshotView {
        display: none;
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    SnapshotView #snap-benchmarks {
        height: 3;
        margin-bottom: 1;
        padding: 0 1;
        background: $surface;
        align: left middle;
    }
    SnapshotView #snap-bench-text {
        width: 1fr;
        overflow: hidden;
    }
    SnapshotView #snap-bench-refresh {
        min-width: 11;
        max-width: 11;
        height: 3;
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
    SnapshotView #snap-recent-label {
        margin-bottom: 1;
    }
    SnapshotView #snap-recent-pills {
        height: auto;
        margin-top: 0;
    }
    SnapshotView #snap-recent-pills Button {
        min-width: 7;
        max-width: 16;
        height: 3;
        margin-right: 1;
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
            yield BenchmarkTicker(id="snap-bench-text")
            yield Button("Refresh", id="snap-bench-refresh")

        with Horizontal(id="snap-middle"):
            with Vertical(id="snap-watchlist-pane"):
                yield Static("[bold]── Watchlist ──[/bold]", id="snap-watchlist-header")
                yield DataTable(id="snap-watchlist-table")
                with Horizontal(id="snap-watchlist-footer"):
                    yield Button("Go to Watchlist →", id="snap-go-watchlist")

        with Vertical(id="snap-recent"):
            yield Label("── Recent / Quick Jump ──", id="snap-recent-label")
            yield Horizontal(id="snap-recent-pills")
        yield Static(
            "── Quick Keys ──\n"
            "  /  Search    p  Portfolio    t  Seasonals    h  Holdings    x  Exposure    c  Concentr.    m  Margin\n"
            "  r  Risk      d  Documents    Esc  Home       w  Watch       s  Source     ^I  IBKR          q  Quit",
            id="snap-keys",
        )

    def on_mount(self) -> None:
        table = self.query_one("#snap-watchlist-table", DataTable)
        table.add_column("Ticker", width=7)
        table.add_column("Fund Name", width=22)
        table.add_column("YTD", width=8)
        table.add_column("Top-10 Wt", width=10)
        table.add_column("Eff N", width=6)
        table.cursor_type = "row"
        # display starts as none via CSS — first paint never shows this widget.
        # ContentSwitcher restores display=True when current="home" is set.

    # ── Public refresh entry point ─────────────────────────────────────────

    def refresh_all(self) -> None:
        """Re-render all panels. Safe to call from navigate_to() and _on_splash_dismissed()."""
        self._render_benchmarks()
        self._load_watchlist()
        self.run_worker(self._render_recent(), exclusive=True, group="snap-recent", name="snap-recent")

    # ── Benchmark Strip ────────────────────────────────────────────────────

    def _render_benchmarks(self) -> None:
        from etfray.db.database import get_cached_etf_profile
        from etfray.data.market_data_service import get_etf_profile

        parts: list[str] = []
        for ticker in BENCHMARK_TICKERS:
            profile = get_etf_profile(ticker)
            if profile and profile.ytd_return is not None:
                ytd = profile.ytd_return
                sign = "+" if ytd >= 0 else ""
                color = "green" if ytd >= 0 else "red"
                parts.append(f"{ticker} [{color}]{sign}{ytd * 100:.1f}%[/{color}] YTD")

        if parts:
            text = "  ".join(parts)
        else:
            text = "SPY · QQQ · AGG · GLD — open any ETF to populate cache"

        self.query_one("#snap-bench-text", BenchmarkTicker).set_content(text)

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
        self.run_worker(self._watchlist_worker(), exclusive=True, group="snap-watchlist", name="snap-watchlist")

    async def _watchlist_worker(self) -> None:
        from asyncio import to_thread

        import io

        import pandas as pd

        from etfray.db.database import (
            get_cached_etf,
            get_cached_holdings,
            get_watchlist,
        )
        from etfray.data.market_data_service import get_etf_profile
        from etfray.domain.etf_analytics import calculate_concentration

        tickers = get_watchlist("default")
        table = self.query_one("#snap-watchlist-table", DataTable)
        table.clear()

        if not tickers:
            table.add_row("—", "No tickers in watchlist — open Search and press W", "—", "—", "—", key="none")
            return

        for ticker in tickers:
            row_data: dict[str, str] = {
                "fund_name": "—",
                "ytd": "—",
                "top10": "—",
            "eff_n": "—",
        }

            cached_etf = await to_thread(get_cached_etf, ticker)
            if cached_etf:
                row_data["fund_name"] = cached_etf.fund_name[:25]

            profile = await to_thread(get_etf_profile, ticker)
            if profile and profile.ytd_return is not None:
                ytd = profile.ytd_return
                sign = "+" if ytd >= 0 else ""
                color = "green" if ytd >= 0 else "red"
                row_data["ytd"] = f"[{color}]{sign}{ytd * 100:.1f}%[/{color}]"

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

            table.add_row(
                ticker,
                row_data["fund_name"],
                row_data["ytd"],
                row_data["top10"],
                row_data["eff_n"],
                key=ticker,
            )

    # ── Recent ETFs ────────────────────────────────────────────────────────

    async def _render_recent(self) -> None:
        from etfray.db.database import get_note

        note = get_note("system", "recent_etfs")
        tickers: list[str] = []
        if note:
            try:
                tickers = json.loads(note.content)
            except (json.JSONDecodeError, AttributeError):
                pass

        pills = self.query_one("#snap-recent-pills", Horizontal)
        # Await removal so the node list is cleared before we mount new buttons
        await pills.query(Button).remove()

        if tickers:
            for t in tickers:
                await pills.mount(Button(t, id=f"snap-recent-btn-{t}", variant="default"))
        await pills.mount(Button("Search →", id="snap-recent-search", variant="primary"))

    # ── Event handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "snap-bench-refresh":
            threading.Thread(target=self._fetch_benchmarks_in_thread, daemon=True).start()
            self.app.notify("Refreshing benchmarks…", timeout=8)
        elif bid == "snap-go-watchlist":
            self.app.navigate_to("workspace-watchlist")
        elif bid and bid.startswith("snap-recent-btn-"):
            ticker = bid.removeprefix("snap-recent-btn-")
            self.app.navigate_to_etf(ticker)
        elif bid == "snap-recent-search":
            self.app.navigate_to("research-search")

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
