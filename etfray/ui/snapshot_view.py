"""Snapshot Home View — startup landing screen for ETFray."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

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


def _fmt_pct(value: float | None, *, width: int = 7) -> str:
    """Format a decimal fraction as a coloured Rich percent string, or '—'."""
    if value is None:
        return "—"
    pct = value * 100
    sign = "+" if pct >= 0 else ""
    color = "green" if pct >= 0 else "red"
    return f"[{color}]{sign}{pct:.1f}%[/{color}]"


def _age_label(ts: int | None) -> str:
    """Return a human-readable age string from a Unix epoch timestamp."""
    if ts is None:
        return ""
    try:
        now = datetime.now(tz=timezone.utc).timestamp()
        mins = int((now - ts) / 60)
        if mins < 60:
            return f"{mins}m ago"
        hrs = mins // 60
        if hrs < 24:
            return f"{hrs}h ago"
        return f"{hrs // 24}d ago"
    except Exception:
        return ""


def _date_label(ts: int | None) -> str:
    """Return a short calendar date string from a Unix epoch timestamp.

    Examples: "today", "Fri May 23", "May 23 2024"
    """
    if ts is None:
        return ""
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        today = datetime.now().date()
        d = dt.date()
        if d == today:
            return "today"
        if d.year == today.year:
            return dt.strftime("%a %b %-d")  # e.g. "Fri May 23"
        return dt.strftime("%b %-d %Y")      # e.g. "May 23 2024"
    except Exception:
        return ""


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
        height: 22;
        margin-bottom: 1;
    }
    SnapshotView #snap-watchlist-pane {
        width: 2fr;
        height: 1fr;
        border: solid $primary-background;
        padding: 1;
    }
    SnapshotView #snap-watchlist-header {
        height: 1;
        margin-bottom: 1;
    }
    SnapshotView #snap-watchlist-table {
        height: 1fr;
        min-height: 6;
    }
    SnapshotView #snap-watchlist-footer {
        height: 3;
        margin-top: 1;
    }
    SnapshotView #snap-watchlist-footer Button {
        min-width: 18;
    }
    SnapshotView #snap-movers-pane {
        width: 1fr;
        height: 1fr;
        border: solid $primary-background;
        padding: 1;
        margin-left: 1;
    }
    SnapshotView #snap-movers-table {
        height: 1fr;
        min-height: 6;
    }
    SnapshotView #snap-movers-header {
        height: 1;
        margin-bottom: 1;
    }
    SnapshotView #snap-movers-footer {
        height: 4;
        margin-top: 1;
    }
    SnapshotView #snap-movers-status {
        height: 1;
        margin-bottom: 0;
        color: $text-muted;
    }
    SnapshotView #snap-movers-footer Button {
        min-width: 11;
    }
    SnapshotView #snap-seasonal-strip {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
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
    _last_movers_click: tuple[str, float] | None = None

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

            with Vertical(id="snap-movers-pane"):
                yield Static("[bold]── ETF Movers ──[/bold]", id="snap-movers-header")
                yield DataTable(id="snap-movers-table")
                with Vertical(id="snap-movers-footer"):
                    yield Static("", id="snap-movers-status")
                    yield Button("Refresh", id="snap-movers-refresh")

        yield Static("", id="snap-seasonal-strip")

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
        # Watchlist table
        wl = self.query_one("#snap-watchlist-table", DataTable)
        wl.add_column("Ticker", width=7)
        wl.add_column("Fund Name", width=22)
        wl.add_column("YTD", width=8)
        wl.add_column("Top-10 Wt", width=10)
        wl.add_column("Eff N", width=6)
        wl.add_column("HHI", width=8)
        wl.add_column("Top Sector", width=18)
        wl.cursor_type = "row"

        # Movers table — gainers section header + 5 rows, losers section header + 5 rows
        mv = self.query_one("#snap-movers-table", DataTable)
        mv.add_column("Symbol", width=7)
        mv.add_column("Chg %", width=8)
        mv.add_column("Name", width=20)
        mv.cursor_type = "row"

    # ── Public refresh entry point ─────────────────────────────────────────

    def refresh_all(self) -> None:
        """Re-render all panels. Safe to call from navigate_to() and _on_splash_dismissed()."""
        self._load_benchmarks()
        self._load_watchlist()
        self._load_movers()
        self.run_worker(self._render_recent(), exclusive=True, group="snap-recent", name="snap-recent")

    # ── Benchmark Marquee ─────────────────────────────────────────────────

    def _load_benchmarks(self) -> None:
        threading.Thread(target=self._fetch_benchmarks_in_thread, daemon=True).start()

    def _render_benchmarks(self) -> None:
        from etfray.data.market_data_service import get_etf_profile

        parts: list[str] = []
        for ticker in BENCHMARK_TICKERS:
            profile, _ = get_etf_profile(ticker)
            if profile and profile.ytd_return is not None:
                ytd = profile.ytd_return
                color = "green" if ytd >= 0 else "red"
                from etfray.domain.overview_format import fmt_pct
                parts.append(f"{ticker} [{color}]{fmt_pct(ytd, signed=True)}[/{color}] YTD")

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
                get_etf_profile(ticker)  # result ignored; warms the cache
            except Exception:
                pass
        self.app.call_from_thread(self._render_benchmarks)

    # ── ETF Movers Panel ──────────────────────────────────────────────────

    def _load_movers(self, force_refresh: bool = False) -> None:
        self.run_worker(
            self._movers_worker(force_refresh=force_refresh),
            exclusive=True,
            group="snap-movers",
            name="snap-movers",
        )

    async def _movers_worker(self, *, force_refresh: bool = False) -> None:
        from asyncio import to_thread

        from etfray.data.screener_service import get_etf_movers

        mv = self.query_one("#snap-movers-table", DataTable)
        status = self.query_one("#snap-movers-status", Static)
        mv.clear()

        movers = await to_thread(get_etf_movers, force_refresh=force_refresh)

        if movers is None:
            mv.add_row("—", "—", "Error fetching movers")
            status.update("[red]fetch error[/red]")
            return

        # Gainers section
        mv.add_row("[bold]▲ Gainers[/bold]", "", "", key="_gainers_hdr")
        for m in movers.gainers:
            mv.add_row(
                m.symbol,
                _fmt_pct(m.change_pct),
                m.name[:20],
                key=f"g_{m.symbol}",
            )

        # Losers section
        mv.add_row("[bold]▼ Losers[/bold]", "", "", key="_losers_hdr")
        for m in movers.losers:
            mv.add_row(
                m.symbol,
                _fmt_pct(m.change_pct),
                m.name[:20],
                key=f"l_{m.symbol}",
            )

        # Status / stale banner
        all_movers = movers.gainers + movers.losers
        ts = next((m.last_trade_ts for m in all_movers if m.last_trade_ts), None)
        age = _age_label(ts)
        date = _date_label(ts)
        if movers.is_stale:
            label = f"Last session · {date}" if date else f"Last session ({age})"
            status.update(f"[yellow]{label}[/yellow]")
        else:
            if date == "today":
                label = f"today · {age}" if age else "today"
            else:
                label = f"{date} · {age}" if date and age else (date or age)
            status.update(f"[dim]{label}[/dim]" if label else "")

    # ── Watchlist Summary (async worker) ──────────────────────────────────

    def _load_watchlist(self) -> None:
        self.run_worker(self._watchlist_worker(), exclusive=True, group="snap-watchlist", name="snap-watchlist")

    async def _watchlist_worker(self) -> None:
        import io
        from asyncio import to_thread

        import pandas as pd

        from etfray.data.market_data_service import get_etf_profile
        from etfray.db.database import (
            get_cached_etf,
            get_cached_holdings,
            get_watchlist,
        )
        from etfray.domain.etf_analytics import calculate_concentration, calculate_group_concentration

        tickers = get_watchlist("default")
        table = self.query_one("#snap-watchlist-table", DataTable)
        table.clear()

        if not tickers:
            table.add_row("—", "No tickers in watchlist — open Search and press W", "—", "—", "—", "—", "—", key="none")
            return

        for ticker in tickers:
            row_data: dict[str, str] = {
                "fund_name": "—",
                "ytd": "—",
                "top10": "—",
                "eff_n": "—",
                "hhi": "—",
                "top_sector": "—",
            }

            cached_etf = await to_thread(get_cached_etf, ticker)
            if cached_etf:
                row_data["fund_name"] = cached_etf.fund_name[:25]

            profile, _ = await to_thread(get_etf_profile, ticker)
            if profile and profile.ytd_return is not None:
                ytd = profile.ytd_return
                color = "green" if ytd >= 0 else "red"
                from etfray.domain.overview_format import fmt_pct
                row_data["ytd"] = f"[{color}]{fmt_pct(ytd, signed=True)}[/{color}]"

            cached_h = await to_thread(get_cached_holdings, ticker)
            if cached_h and cached_h.get("holdings_json"):
                try:
                    df = pd.read_json(io.StringIO(cached_h["holdings_json"]))
                    if not df.empty:
                        conc = calculate_concentration(df)
                        row_data["top10"] = f"{conc.top10_weight:.1f}%"
                        row_data["eff_n"] = f"{conc.effective_n:.0f}"
                        row_data["hhi"] = f"{conc.hhi:.4f}"

                        # Try common sector column names
                        for sector_col in ("lei_sector", "sector", "gics_sector"):
                            gc = calculate_group_concentration(df, sector_col)
                            if gc is not None and gc.top1_name:
                                top = gc.top1_name[:18]
                                row_data["top_sector"] = top
                                break
                except Exception:
                    pass

            table.add_row(
                ticker,
                row_data["fund_name"],
                row_data["ytd"],
                row_data["top10"],
                row_data["eff_n"],
                row_data["hhi"],
                row_data["top_sector"],
                key=ticker,
            )

    # ── Seasonal Spotlight ────────────────────────────────────────────────

    async def _load_seasonal_spotlight(self) -> None:
        from asyncio import to_thread

        from etfray.data.price_history_service import get_price_history
        from etfray.db.database import get_watchlist
        from etfray.domain.seasonals_analytics import compute_monthly_returns_table

        tickers = get_watchlist("default")
        if not tickers:
            return

        now = datetime.now()
        current_month = now.month
        month_name = datetime(2000, current_month, 1).strftime("%b")
        parts: list[str] = []

        for ticker in tickers:
            df, _ = await to_thread(get_price_history, ticker, "max")
            if df is None:
                continue
            from etfray.domain.seasonals_analytics import adj_close_series
            prices = adj_close_series(df)
            if prices.empty:
                continue
            table = compute_monthly_returns_table(prices)
            rises = table.rises.get(current_month, 0)
            falls = table.falls.get(current_month, 0)
            total = rises + falls
            if total == 0:
                continue
            win_rate = rises / total
            color = "green" if win_rate > 0.5 else ("red" if win_rate < 0.5 else "dim")
            # Historical frequency label: "↑6/15" instead of ambiguous "falls 40%"
            freq_label = f"[{color}]↑{rises}/{total} yrs[/{color}]"
            # Current MTD return for this month (may be partial if month in progress)
            cur_ret = table.monthly.get(now.year, {}).get(current_month)
            if cur_ret is not None:
                mtd_sign = "+" if cur_ret >= 0 else ""
                mtd_color = "green" if cur_ret > 0 else ("red" if cur_ret < 0 else "dim")
                mtd_label = f" [{mtd_color}]{mtd_sign}{cur_ret * 100:.1f}% MTD[/{mtd_color}]"
            else:
                mtd_label = ""
            parts.append(f"[bold]{ticker}[/bold] {freq_label}{mtd_label}")

        strip = self.query_one("#snap-seasonal-strip", Static)
        if parts:
            strip.update(f"[dim]{month_name} seasonals:[/dim]  " + "   ".join(parts))
        else:
            strip.update("")

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
        await pills.query(Button).remove()

        if tickers:
            for t in tickers:
                await pills.mount(Button(t, id=f"snap-recent-btn-{t}", variant="default"))
        await pills.mount(Button("Search →", id="snap-recent-search", variant="primary"))

        # Seasonal spotlight depends on watchlist — kick it off after recent is loaded
        self.run_worker(
            self._load_seasonal_spotlight(),
            exclusive=True,
            group="snap-seasonal",
            name="snap-seasonal",
        )

    # ── Event handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "snap-bench-refresh":
            self._load_benchmarks()
            self.app.notify("Refreshing benchmarks…", timeout=8)
        elif bid == "snap-movers-refresh":
            self._load_movers(force_refresh=True)
            self.app.notify("Refreshing ETF movers…", timeout=8)
        elif bid == "snap-go-watchlist":
            self.app.navigate_to("workspace-watchlist")
        elif bid and bid.startswith("snap-recent-btn-"):
            ticker = bid.removeprefix("snap-recent-btn-")
            self.app.navigate_to_etf(ticker)
        elif bid == "snap-recent-search":
            self.app.navigate_to("research-search")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.control.id == "snap-movers-table" and event.row_key:
            key = str(event.row_key.value)
            if not key.startswith(("g_", "l_")):
                return  # section header row
            ticker = key[2:]
            now = time.monotonic()
            if (
                self._last_movers_click
                and self._last_movers_click[0] == ticker
                and now - self._last_movers_click[1] < _DOUBLE_CLICK_SECONDS
            ):
                self._last_movers_click = None
                self.app.navigate_to_etf(ticker)
            else:
                self._last_movers_click = (ticker, now)
            return

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
