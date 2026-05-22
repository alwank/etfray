"""Startup splash screen with boot sequence animation."""

import threading
from time import sleep

from textual.app import ComposeResult
from textual.containers import Center, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Static

LOGO = """\
 ███████╗████████╗███████╗██████╗  █████╗ ██╗   ██╗
 ██╔════╝╚══██╔══╝██╔════╝██╔══██╗██╔══██╗╚██╗ ██╔╝
 █████╗     ██║   █████╗  ██████╔╝███████║ ╚████╔╝
 ██╔══╝     ██║   ██╔══╝  ██╔══██╗██╔══██║  ╚██╔╝
 ███████╗   ██║   ██║     ██║  ██║██║  ██║   ██║
 ╚══════╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝
"""

ICONS = {"pending": "⋯", "running": "⟳", "ok": "✓", "fail": "✗", "warn": "⚠"}


class StatusLine(Static):
    DEFAULT_CSS = """
    StatusLine { height: 1; width: 100%; content-align: left middle; }
    """

    def __init__(self, label: str, **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._state = "pending"
        self._detail = ""

    def set_state(self, state: str, detail: str = "") -> None:
        self._state = state
        self._detail = detail
        self.update(self._render_line())

    def _render_line(self) -> str:
        icon = ICONS.get(self._state, "?")
        style = {"ok": "green", "fail": "red", "warn": "yellow", "running": "cyan"}.get(self._state, "dim")
        line = f"  [{style}]{icon}[/{style}] {self._label}"
        if self._detail:
            line += f"  [dim]{self._detail}[/dim]"
        return line

    def render(self) -> str:
        return self._render_line()


class SplashScreen(Screen):
    DEFAULT_CSS = """
    SplashScreen {
        align: center middle;
        background: $surface;
    }
    #splash-logo {
        text-align: center;
        color: rgb(100, 180, 255);
        margin-bottom: 1;
    }
    #splash-subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 2;
    }
    #splash-status {
        width: 50;
        height: auto;
    }
    """

    BINDINGS = []

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield Static(LOGO, id="splash-logo")
            with Center():
                yield Static("etfray", id="splash-subtitle")
            with Center():
                with Vertical(id="splash-status"):
                    yield StatusLine("Database", id="status-db")
                    yield StatusLine("Settings", id="status-settings")
                    yield StatusLine("IBKR Connection", id="status-ibkr")
                    yield StatusLine("Cache", id="status-cache")

    def on_mount(self) -> None:
        self._run_startup()

    def _run_startup(self) -> None:
        threading.Thread(target=self._startup_sequence, daemon=True).start()

    def _set_status(self, widget_id: str, state: str, detail: str = "") -> None:
        self.query_one(f"#{widget_id}", StatusLine).set_state(state, detail)

    def _startup_sequence(self) -> None:
        # 1. Database init
        self.app.call_from_thread(self._set_status, "status-db", "running")
        sleep(0.1)
        try:
            from etfray.db.database import get_db
            get_db().close()
            self.app.call_from_thread(self._set_status, "status-db", "ok")
        except Exception as e:
            self.app.call_from_thread(self._set_status, "status-db", "fail", str(e))
        sleep(0.1)

        # 2. Settings validation
        self.app.call_from_thread(self._set_status, "status-settings", "running")
        sleep(0.1)
        try:
            from etfray.db.database import load_settings
            s = load_settings()
            warnings = []
            if not s.edgar_identity:
                warnings.append("EDGAR identity not set")
            if not (1 <= s.ibkr_port <= 65535):
                warnings.append("Invalid IBKR port")
            if warnings:
                self.app.call_from_thread(self._set_status, "status-settings", "warn", "; ".join(warnings))
            else:
                self.app.call_from_thread(self._set_status, "status-settings", "ok")
        except Exception as e:
            self.app.call_from_thread(self._set_status, "status-settings", "fail", str(e))
        sleep(0.1)

        # 3. IBKR — skip auto-connect (use Ctrl+I to connect manually)
        self.app.call_from_thread(self._set_status, "status-ibkr", "ok", "Manual (Ctrl+I)")
        sleep(0.1)

        # 4. Cache warmup
        self.app.call_from_thread(self._set_status, "status-cache", "running")
        try:
            from etfray.db.database import get_all_watchlists, get_cached_holdings
            watchlists = get_all_watchlists()
            tickers = {t for wl in watchlists.values() for t in wl}
            for t in list(tickers)[:10]:
                get_cached_holdings(t)
            self.app.call_from_thread(self._set_status, "status-cache", "ok", f"{len(tickers)} tickers")
        except Exception as e:
            self.app.call_from_thread(self._set_status, "status-cache", "warn", str(e))
        sleep(0.1)

        # Dismiss
        sleep(0.3)
        self.app.call_from_thread(self.dismiss)
