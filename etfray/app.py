from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Footer, Header, Static, Tree

try:
    import textual_image  # noqa: F401 — register terminal graphics before App.run
except ImportError:
    pass

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
from etfray.ui.research.documents_view import DocumentsView
from etfray.ui.research.exposure_view import ExposureView
from etfray.ui.research.fees_view import FeesView
from etfray.ui.research.holdings_view import HoldingsView
from etfray.ui.research.overview_view import OverviewView
from etfray.ui.research.risk_view import RiskView
from etfray.ui.research.search_view import SearchView
from etfray.ui.research.seasonals_view import SeasonalsView
from etfray.ui.splash_screen import SplashScreen
from etfray.ui.workspace.exports_view import ExportsView
from etfray.ui.workspace.settings_view import SettingsView
from etfray.ui.workspace.watchlist_view import WatchlistView


class Sidebar(Widget):
    DEFAULT_CSS = """
    Sidebar {
        width: 28;
        dock: left;
        border-right: solid $primary-background;
        padding: 1;
    }
    Sidebar .sidebar-title {
        text-style: bold;
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("ETFray", classes="sidebar-title")
        tree: Tree[str] = Tree("", id="nav-tree")
        tree.show_root = False
        tree.root.expand()

        research = tree.root.add("Research", expand=True)
        research.add_leaf("ETF Search", data="research-search")
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
    #app-body {
        height: 1fr;
    }
    #content {
        width: 1fr;
    }
    #content VerticalScroll,
    #content Vertical {
        height: auto;
    }
    #content VerticalScroll Horizontal {
        height: auto;
    }
    #content ContentSwitcher {
        height: 1fr;
        width: 1fr;
    }
    #content SeasonalsView {
        height: 1fr;
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
        Binding("escape", "nav('welcome')", "Back"),
        Binding("w", "add_to_watchlist", "Watch"),
        Binding("ctrl+i", "connect_ibkr", "Connect IBKR"),
        Binding("s", "cycle_source", "Source"),
    ]

    _current_etf: str | None = None
    _ibkr_connected: bool = False
    _data_source: str = "auto"

    def compose(self) -> ComposeResult:
        from etfray.db.database import load_settings
        self._data_source = load_settings().data_source or "auto"

        yield Header()
        with Horizontal(id="app-body"):
            yield Sidebar()
            with ContentSwitcher(initial="welcome", id="content"):
                yield Static(
                    "Welcome to ETFray\n\n"
                    "Use the sidebar or press / to search for an ETF.\n\n"
                    "Keyboard shortcuts:\n"
                    "  /  Search        p  Portfolio\n"
                    "  t  Seasonals    h  Holdings\n"
                    "  x  Exposure      c  Concentration\n"
                    "  m  Margin        r  Risk          d  Documents\n"
                    "  q  Quit          Esc Back",
                    id="welcome",
                )
                yield SearchView(id="research-search")
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
        self.push_screen(SplashScreen())

    def on_screen_resume(self) -> None:
        self.screen.refresh(layout=True)

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
        if self._current_etf and switcher.current and switcher.current.startswith("research-") and switcher.current != "research-search":
            self._load_view(switcher.current)

    def navigate_to(self, view_id: str) -> None:
        try:
            switcher = self.query_one("#content", ContentSwitcher)
        except Exception:
            return
        if switcher.query(f"#{view_id}"):
            switcher.current = view_id
            if self._current_etf and view_id.startswith("research-") and view_id != "research-search":
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
        self.navigate_to("research-overview")

    def action_nav(self, view_id: str) -> None:
        self.navigate_to(view_id)

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
        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.db.database import load_settings

        s = load_settings()
        svc = get_ibkr_service()

        def _do_connect():
            return svc.connect(s.ibkr_host, s.ibkr_port, s.ibkr_client_id)

        import threading
        def _connect_thread():
            ok = _do_connect()
            self.call_from_thread(self._on_ibkr_connected, ok, svc)

        threading.Thread(target=_connect_thread, daemon=True).start()
        self.notify("Connecting to IBKR...", timeout=10)

    def _on_ibkr_connected(self, ok: bool, svc) -> None:
        if ok:
            self._ibkr_connected = True
            self.query_one(StatusBar).refresh()
            self.notify("IBKR connected successfully")
            self.query_one("#portfolio-overview", PortfolioOverviewView)._refresh()
        else:
            err = getattr(svc, '_last_error', 'Unknown error')
            self.notify(f"IBKR connection failed: {err}", severity="error")


def main():
    app = ETFTerminalApp()
    app.run()


if __name__ == "__main__":
    main()
