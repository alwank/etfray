import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Footer, Header, Static, Tree

try:
    import textual_image  # noqa: F401 — register terminal graphics before App.run
    from textual_image.widget import Image as TermImage

    _HAS_IMAGE = True
except ImportError:
    _HAS_IMAGE = False

from etfray.ui.commands import ETFCommands
from etfray.ui.portfolio.concentration_view import PortfolioConcentrationView
from etfray.ui.portfolio.exposure_view import PortfolioExposureView
from etfray.ui.portfolio.lookthrough_view import LookthroughView
from etfray.ui.portfolio.margin_view import MarginView
from etfray.ui.portfolio.overview_view import PortfolioOverviewView
from etfray.ui.portfolio.positions_view import PositionsView
from etfray.ui.portfolio.risk_view import PortfolioRiskView
from etfray.ui.research.compare_view import CompareView
from etfray.ui.research.concentration_view import ConcentrationView
from etfray.ui.research.discovery_view import DiscoveryView
from etfray.ui.research.documents_view import DocumentsView
from etfray.ui.research.exposure_view import ExposureView
from etfray.ui.research.fees_view import FeesView
from etfray.ui.research.holdings_view import HoldingsView
from etfray.ui.research.overview_view import OverviewView
from etfray.ui.research.risk_view import RiskView
from etfray.ui.research.seasonals_view import SeasonalsView
from etfray.ui.snapshot_view import SnapshotView
from etfray.ui.splash_screen import LOGO_SMALL, SplashScreen
from etfray.ui.workspace.exports_view import ExportsView
from etfray.ui.workspace.settings_view import SettingsView
from etfray.ui.workspace.watchlist_view import WatchlistView

_LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"


class Sidebar(Widget):
    DEFAULT_CSS = """
    Sidebar {
        width: 28;
        dock: left;
        border-right: solid $primary-background;
        padding: 1;
    }
    Sidebar #sidebar-logo {
        height: 5;
        width: 26;
        padding-bottom: 1;
    }
    Sidebar .sidebar-title {
        color: rgb(100, 180, 255);
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        if _HAS_IMAGE and _LOGO_PATH.exists():
            yield TermImage(_LOGO_PATH, id="sidebar-logo")
        else:
            yield Static(LOGO_SMALL, classes="sidebar-title")
        tree: Tree[str] = Tree("", id="nav-tree")
        tree.show_root = False
        tree.root.expand()

        tree.root.add_leaf("Home", data="home")

        research = tree.root.add("Research", expand=True)
        research.add_leaf("Search", data="research-search")
        research.add_leaf("Overview", data="research-overview")
        research.add_leaf("Seasonals", data="research-seasonals")
        research.add_leaf("Holdings", data="research-holdings")
        research.add_leaf("Exposure", data="research-exposure")
        research.add_leaf("Concentration", data="research-concentration")
        research.add_leaf("Fees", data="research-fees")
        research.add_leaf("Risk", data="research-risk")
        research.add_leaf("Documents", data="research-documents")
        research.add_leaf("Compare", data="research-compare")

        portfolio = tree.root.add("Portfolio", expand=True)
        portfolio.add_leaf("Overview", data="portfolio-overview")
        portfolio.add_leaf("Positions", data="portfolio-positions")
        portfolio.add_leaf("ETF Lookthrough", data="portfolio-lookthrough")
        portfolio.add_leaf("Exposure", data="portfolio-exposure")
        portfolio.add_leaf("Concentration", data="portfolio-concentration")
        portfolio.add_leaf("Margin", data="portfolio-margin")
        portfolio.add_leaf("Risk", data="portfolio-risk")

        workspace = tree.root.add("Workspace", expand=True)
        workspace.add_leaf("Watchlist", data="workspace-watchlist")
        workspace.add_leaf("Exports", data="workspace-exports")
        workspace.add_leaf("Settings", data="workspace-settings")

        yield tree


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    """

    def render(self) -> str:
        app = self.app
        etf = getattr(app, "_current_etf", None)
        etf_str = f"ETF: {etf}" if etf else "No ETF selected"
        ibkr = getattr(app, "_ibkr_connected", False)
        ibkr_str = "IBKR: Connected" if ibkr else "IBKR: Disconnected"
        source = getattr(app, "_data_source", "auto").capitalize()

        freshness = ""
        if etf:
            from etfray.db.database import get_cached_holdings, load_settings

            cached = get_cached_holdings(etf)
            if cached and cached.get("as_of_date"):
                from datetime import date, datetime

                try:
                    s = load_settings()
                    as_of = datetime.fromisoformat(cached["as_of_date"]).date()
                    days = (date.today() - as_of).days
                    if days < s.freshness_days_fresh:
                        freshness = f" | Data: Fresh ({cached['as_of_date'][:10]})"
                    elif days < s.freshness_days_acceptable:
                        freshness = f" | Data: Acceptable ({cached['as_of_date'][:10]})"
                    else:
                        freshness = f" | Data: Stale ({cached['as_of_date'][:10]})"
                except (ValueError, TypeError):
                    pass

        return f"{ibkr_str} | Source: {source} [s] | {etf_str}{freshness}"


class ETFTerminalApp(App):
    TITLE = "ETFray"
    COMMANDS = {ETFCommands}
    CSS = """
    Screen {
        layout: vertical;
    }
    /* Pre-splash: hide all main screen content so the terminal is blank
       before push_screen(SplashScreen) fires. CSS is applied before the
       first render; everything is revealed atomically in _on_splash_dismissed. */
    Header { display: none; }
    #app-body {
        display: none;
        height: 1fr;
    }
    StatusBar { display: none; }
    Footer { display: none; }
    #content {
        width: 1fr;
        height: 1fr;
    }
    /* Nested toolbars only — do not collapse top-level content views */
    #content ContentSwitcher VerticalScroll Horizontal,
    #content ContentSwitcher Vertical Horizontal {
        height: auto;
    }
    #content ContentSwitcher {
        height: 1fr;
        width: 1fr;
    }
    /* Direct page roots only — avoid stretching nested toolbars/tables */
    #content ContentSwitcher > Static,
    #content ContentSwitcher > SnapshotView,
    #content ContentSwitcher > DiscoveryView,
    #content ContentSwitcher > OverviewView,
    #content ContentSwitcher > SeasonalsView,
    #content ContentSwitcher > HoldingsView,
    #content ContentSwitcher > ExposureView,
    #content ContentSwitcher > ConcentrationView,
    #content ContentSwitcher > FeesView,
    #content ContentSwitcher > RiskView,
    #content ContentSwitcher > DocumentsView,
    #content ContentSwitcher > CompareView,
    #content ContentSwitcher > PortfolioOverviewView,
    #content ContentSwitcher > PositionsView,
    #content ContentSwitcher > LookthroughView,
    #content ContentSwitcher > PortfolioExposureView,
    #content ContentSwitcher > PortfolioConcentrationView,
    #content ContentSwitcher > MarginView,
    #content ContentSwitcher > PortfolioRiskView,
    #content ContentSwitcher > ExportsView,
    #content ContentSwitcher > WatchlistView,
    #content ContentSwitcher > SettingsView {
        height: 1fr;
        min-height: 1fr;
    }

    /* Neutral buttons app-wide (Textual 1.0 3D button style) */
    Button {
        color: $text-muted;
        background: $surface;
        border: none;
        border-top: tall $surface-lighten-1;
        border-bottom: tall $surface-darken-1;

        &:hover {
            color: $text;
            background: $surface-darken-1;
            border-top: tall $surface;
            border-bottom: tall $surface-darken-1;
        }

        &:focus {
            text-style: bold;
        }

        &.-primary,
        &.-success,
        &.-warning,
        &.-error {
            color: $text-muted;
            background: $surface;
            border: none;
            border-top: tall $surface-lighten-1;
            border-bottom: tall $surface-darken-1;

            &:hover {
                color: $text;
                background: $surface-darken-1;
                border-top: tall $surface;
                border-bottom: tall $surface-darken-1;
            }
        }

        &.-on {
            color: $text;
            background: $surface-darken-1;
            border: none;
            border-top: tall $surface-darken-1;
            border-bottom: tall $surface-lighten-1;
            text-style: bold;
        }
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("slash", "nav('research-search')", "Search", key_display="/"),
        Binding("p", "nav('portfolio-overview')", "Portfolio"),
        Binding("t", "nav('research-seasonals')", "Seasonals"),
        Binding("h", "nav('research-holdings')", "Holdings"),
        Binding("x", "nav('research-exposure')", "Exposure"),
        Binding("c", "nav('research-concentration')", "Concentration"),
        Binding("m", "nav('portfolio-margin')", "Margin"),
        Binding("r", "nav('research-risk')", "Risk"),
        Binding("d", "nav('research-documents')", "Documents"),
        Binding("escape", "nav('home')", "Home"),
        Binding("w", "add_to_watchlist", "Watch"),
        Binding("ctrl+i", "connect_ibkr", "Connect IBKR"),
        Binding("s", "cycle_source", "Source"),
    ]

    _current_etf: str | None = None
    _ibkr_connected: bool = False
    _data_source: str = "auto"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nav_debounce_buf: list[str] = []
        self._nav_debounce_timer = None

    def compose(self) -> ComposeResult:
        from etfray.db.database import load_settings

        self._data_source = load_settings().data_source or "auto"

        yield Header()
        with Horizontal(id="app-body"):
            yield Sidebar()
            with ContentSwitcher(initial="research-search", id="content"):
                yield SnapshotView(id="home")
                yield DiscoveryView(id="research-search")
                yield OverviewView(id="research-overview")
                yield SeasonalsView(id="research-seasonals")
                yield HoldingsView(id="research-holdings")
                yield ExposureView(id="research-exposure")
                yield ConcentrationView(id="research-concentration")
                yield FeesView(id="research-fees")
                yield RiskView(id="research-risk")
                yield DocumentsView(id="research-documents")
                yield CompareView(id="research-compare")
                yield PortfolioOverviewView(id="portfolio-overview")
                yield PositionsView(id="portfolio-positions")
                yield LookthroughView(id="portfolio-lookthrough")
                yield PortfolioExposureView(id="portfolio-exposure")
                yield PortfolioConcentrationView(id="portfolio-concentration")
                yield MarginView(id="portfolio-margin")
                yield PortfolioRiskView(id="portfolio-risk")

                yield ExportsView(id="workspace-exports")
                yield WatchlistView(id="workspace-watchlist")
                yield SettingsView(id="workspace-settings")
        yield StatusBar()
        yield Footer()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data:
            self.navigate_to(event.node.data)

    def on_mount(self) -> None:
        self.push_screen(SplashScreen(), callback=self._on_splash_dismissed)

    def on_unmount(self) -> None:
        from etfray.db.database import close_db

        close_db()

    def on_screen_resume(self) -> None:
        self.screen.refresh(layout=True)

    def _on_splash_dismissed(self, _result=None) -> None:
        # Reveal all main screen widgets hidden by CSS pre-splash
        self.query_one(Header).display = True
        self.query_one("#app-body", Horizontal).display = True
        self.query_one(StatusBar).display = True
        self.query_one(Footer).display = True
        # Switch to home and populate data in the same tick
        switcher = self.query_one("#content", ContentSwitcher)
        switcher.current = "home"
        snapshot = self.query_one("#home", SnapshotView)
        snapshot.refresh_all()
        self.call_after_refresh(self._refresh_home_after_splash)

    def _refresh_home_after_splash(self) -> None:
        self.screen.refresh(layout=True)
        for sel in ("#sidebar-logo", ".sidebar-title"):
            try:
                self.query_one(sel).refresh()
                break
            except Exception:
                pass
        if self._ibkr_connected:
            self.query_one(StatusBar).refresh()
            self.query_one("#portfolio-overview", PortfolioOverviewView)._refresh()

    def _connect_ibkr_blocking(self) -> tuple[bool, object]:
        """Connect to IBKR using saved settings. Blocking — call from a worker thread."""
        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.db.database import load_settings

        s = load_settings()
        svc = get_ibkr_service()
        ok = svc.connect(s.ibkr_host, s.ibkr_port, s.ibkr_client_id)
        return ok, svc

    def _mark_ibkr_connected(self) -> None:
        """Lightweight flag update safe to call during splash (no widget refresh)."""
        self._ibkr_connected = True

    def _apply_ibkr_connect_result(self, ok: bool, svc, notify: bool = True) -> None:
        if ok:
            self._ibkr_connected = True
            self.query_one(StatusBar).refresh()
            if notify:
                self.notify("IBKR connected successfully")
            self.query_one("#portfolio-overview", PortfolioOverviewView)._refresh()
        elif notify:
            err = getattr(svc, "_last_error", "Unknown error")
            self.notify(f"IBKR connection failed: {err}", severity="error")

    def action_cycle_source(self) -> None:
        if not self.query("#content"):
            return
        cycle = {"auto": "edgar", "edgar": "web", "web": "auto"}
        self._data_source = cycle[self._data_source]
        from etfray.db.database import load_settings, save_settings

        s = load_settings()
        s.data_source = self._data_source
        save_settings(s)
        self.query_one(StatusBar).refresh()
        self.notify(f"Source: {self._data_source.capitalize()}")
        # Reload current research view with loading state
        switcher = self.query_one("#content", ContentSwitcher)
        if (
            self._current_etf
            and switcher.current
            and switcher.current.startswith("research-")
            and switcher.current != "research-search"
        ):
            self._load_view(switcher.current)

    def navigate_to(self, view_id: str) -> None:
        try:
            switcher = self.query_one("#content", ContentSwitcher)
        except Exception:
            return
        if switcher.query(f"#{view_id}"):
            switcher.current = view_id
            if view_id == "home":
                self.set_timer(0.1, lambda: self.query_one("#home", SnapshotView).refresh_all())
            elif self._current_etf and view_id.startswith("research-") and view_id != "research-search":
                self.set_timer(0.1, lambda: self._load_view(view_id))
            if view_id == "portfolio-overview":
                self.set_timer(0.1, lambda: self.query_one("#portfolio-overview", PortfolioOverviewView)._refresh())
            elif view_id.startswith("portfolio-"):
                self.set_timer(0.1, lambda: self._load_portfolio_view(view_id))
            elif view_id == "workspace-watchlist":
                self.set_timer(0.1, lambda: self.query_one("#workspace-watchlist", WatchlistView).load_data())
        else:
            self.notify(f"View '{view_id}' not yet implemented", severity="warning")

    def _load_view(self, view_id: str) -> None:
        ticker = self._current_etf
        if not ticker:
            return
        view_map = {
            "research-overview": OverviewView,
            "research-seasonals": SeasonalsView,
            "research-holdings": HoldingsView,
            "research-exposure": ExposureView,
            "research-concentration": ConcentrationView,
            "research-fees": FeesView,
            "research-risk": RiskView,
            "research-documents": DocumentsView,
        }
        cls = view_map.get(view_id)
        if cls:
            widget = self.query_one(f"#{view_id}", cls)
            widget.load_etf(ticker)

    def _load_portfolio_view(self, view_id: str) -> None:
        view_map = {
            "portfolio-positions": PositionsView,
            "portfolio-lookthrough": LookthroughView,
            "portfolio-exposure": PortfolioExposureView,
            "portfolio-concentration": PortfolioConcentrationView,
            "portfolio-margin": MarginView,
            "portfolio-risk": PortfolioRiskView,
        }
        cls = view_map.get(view_id)
        if cls:
            widget = self.query_one(f"#{view_id}", cls)
            widget.load_data()

    def navigate_to_etf(self, ticker: str) -> None:
        self._current_etf = ticker
        self.query_one(StatusBar).refresh()
        self._update_recent_etfs(ticker)
        self.navigate_to("research-overview")

    def _update_recent_etfs(self, ticker: str) -> None:
        """Keep a capped, deduped, newest-first recent-ETF list in the notes table."""
        from etfray.db.database import get_note, upsert_note

        note = get_note("system", "recent_etfs")
        try:
            existing: list[str] = json.loads(note.content) if note else []
        except (json.JSONDecodeError, AttributeError):
            existing = []

        deduped = [t for t in existing if t != ticker]
        updated = [ticker] + deduped
        upsert_note("system", "recent_etfs", json.dumps(updated[:5]))

    def action_nav(self, view_id: str) -> None:
        # Terminal graphics (sixel) can inject spurious key events (e.g. ESC, 'c').
        # Debounce: only apply when exactly one nav key arrives in a short window.
        self._nav_debounce_buf.append(view_id)
        if self._nav_debounce_timer:
            self._nav_debounce_timer.stop()
        self._nav_debounce_timer = self.set_timer(0.05, self._apply_debounced_nav)

    def _apply_debounced_nav(self) -> None:
        buf = self._nav_debounce_buf[:]
        self._nav_debounce_buf.clear()
        if len(buf) == 1:
            self.navigate_to(buf[0])

    def action_add_to_watchlist(self) -> None:
        if not self._current_etf:
            self.notify("No ETF selected", severity="warning")
            return
        from etfray.db.database import add_to_watchlist

        if add_to_watchlist("default", self._current_etf):
            self.notify(f"{self._current_etf} added to watchlist")
        else:
            self.notify(f"{self._current_etf} already in watchlist", severity="warning")

    def action_connect_ibkr(self) -> None:
        if self._ibkr_connected:
            self.notify("IBKR already connected")
            return

        import threading

        def _connect_thread():
            ok, svc = self._connect_ibkr_blocking()
            self.call_from_thread(self._apply_ibkr_connect_result, ok, svc)

        threading.Thread(target=_connect_thread, daemon=True).start()
        self.notify("Connecting to IBKR...", timeout=10)


def main():
    app = ETFTerminalApp()
    app.run()


if __name__ == "__main__":
    main()
