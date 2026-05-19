from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static, Tree, ContentSwitcher
from textual.widget import Widget

from etf_terminal.ui.commands import ETFCommands
from etf_terminal.ui.research.search_view import SearchView
from etf_terminal.ui.research.overview_view import OverviewView
from etf_terminal.ui.research.holdings_view import HoldingsView
from etf_terminal.ui.research.exposure_view import ExposureView
from etf_terminal.ui.research.concentration_view import ConcentrationView
from etf_terminal.ui.research.fees_view import FeesView
from etf_terminal.ui.research.risk_view import RiskView
from etf_terminal.ui.research.documents_view import DocumentsView
from etf_terminal.ui.research.compare_view import CompareView
from etf_terminal.ui.workspace.settings_view import SettingsView
from etf_terminal.ui.workspace.watchlists_view import WatchlistsView
from etf_terminal.ui.workspace.notes_view import NotesView
from etf_terminal.ui.workspace.exports_view import ExportsView
from etf_terminal.ui.portfolio.overview_view import PortfolioOverviewView
from etf_terminal.ui.portfolio.positions_view import PositionsView
from etf_terminal.ui.portfolio.lookthrough_view import LookthroughView
from etf_terminal.ui.portfolio.exposure_view import PortfolioExposureView
from etf_terminal.ui.portfolio.concentration_view import PortfolioConcentrationView
from etf_terminal.ui.portfolio.margin_view import MarginView
from etf_terminal.ui.portfolio.risk_view import PortfolioRiskView


class Sidebar(Widget):
    DEFAULT_CSS = """
    Sidebar {
        width: 28;
        dock: left;
        border-right: solid $primary-background;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        tree: Tree[str] = Tree("ETF Terminal", id="nav-tree")
        tree.root.expand()

        research = tree.root.add("Research", expand=True)
        research.add_leaf("ETF Search", data="research-search")
        research.add_leaf("Overview", data="research-overview")
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
        workspace.add_leaf("Watchlists", data="workspace-watchlists")
        workspace.add_leaf("Notes", data="workspace-notes")
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
            from etf_terminal.db.database import get_cached_holdings
            cached = get_cached_holdings(etf)
            if cached and cached.get("as_of_date"):
                from datetime import datetime, date
                try:
                    as_of = datetime.fromisoformat(cached["as_of_date"]).date()
                    days = (date.today() - as_of).days
                    if days < 60:
                        freshness = f" | Data: Fresh ({cached['as_of_date'][:10]})"
                    elif days < 150:
                        freshness = f" | Data: Acceptable ({cached['as_of_date'][:10]})"
                    else:
                        freshness = f" | Data: Stale ({cached['as_of_date'][:10]})"
                except (ValueError, TypeError):
                    pass

        return f"{ibkr_str} | Source: {source} [s] | {etf_str}{freshness}"


class ETFTerminalApp(App):
    TITLE = "ETF Portfolio Terminal"
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
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("slash", "nav('research-search')", "Search", key_display="/"),
        Binding("p", "nav('portfolio-overview')", "Portfolio"),
        Binding("h", "nav('research-holdings')", "Holdings"),
        Binding("x", "nav('research-exposure')", "Exposure"),
        Binding("c", "nav('research-concentration')", "Concentration"),
        Binding("m", "nav('portfolio-margin')", "Margin"),
        Binding("r", "nav('research-risk')", "Risk"),
        Binding("d", "nav('research-documents')", "Documents"),
        Binding("escape", "nav('welcome')", "Back"),
        Binding("ctrl+i", "connect_ibkr", "Connect IBKR"),
        Binding("s", "cycle_source", "Source"),
    ]

    _current_etf: str | None = None
    _ibkr_connected: bool = False
    _data_source: str = "auto"

    def compose(self) -> ComposeResult:
        from etf_terminal.db.database import load_settings
        self._data_source = load_settings().data_source or "auto"

        yield Header()
        with Horizontal(id="app-body"):
            yield Sidebar()
            with ContentSwitcher(initial="welcome", id="content"):
                yield Static(
                    "Welcome to ETF Portfolio Terminal\n\n"
                    "Use the sidebar or press / to search for an ETF.\n\n"
                    "Keyboard shortcuts:\n"
                    "  /  Search        p  Portfolio\n"
                    "  h  Holdings      x  Exposure\n"
                    "  c  Concentration m  Margin\n"
                    "  r  Risk          d  Documents\n"
                    "  q  Quit          Esc Back",
                    id="welcome",
                )
                yield SearchView(id="research-search")
                yield OverviewView(id="research-overview")
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
                yield WatchlistsView(id="workspace-watchlists")
                yield NotesView(id="workspace-notes")
                yield ExportsView(id="workspace-exports")
                yield SettingsView(id="workspace-settings")
        yield StatusBar()
        yield Footer()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data:
            self.navigate_to(event.node.data)

    def action_cycle_source(self) -> None:
        cycle = {"auto": "edgar", "edgar": "zacks", "zacks": "auto"}
        self._data_source = cycle[self._data_source]
        from etf_terminal.db.database import load_settings, save_settings
        s = load_settings()
        s.data_source = self._data_source
        save_settings(s)
        self.query_one(StatusBar).refresh()
        self.notify(f"Source: {self._data_source.capitalize()}")
        # Reload current research view
        switcher = self.query_one("#content", ContentSwitcher)
        if self._current_etf and switcher.current and switcher.current.startswith("research-") and switcher.current != "research-search":
            self._load_view(switcher.current)

    def navigate_to(self, view_id: str) -> None:
        switcher = self.query_one("#content", ContentSwitcher)
        if switcher.query(f"#{view_id}"):
            switcher.current = view_id
            if self._current_etf and view_id.startswith("research-") and view_id != "research-search":
                self.set_timer(0.1, lambda: self._load_view(view_id))
            if view_id.startswith("portfolio-") and view_id != "portfolio-overview":
                self.set_timer(0.1, lambda: self._load_portfolio_view(view_id))
        else:
            self.notify(f"View '{view_id}' not yet implemented", severity="warning")

    def _load_view(self, view_id: str) -> None:
        ticker = self._current_etf
        if not ticker:
            return
        view_map = {
            "research-overview": OverviewView,
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

    def action_connect_ibkr(self) -> None:
        from concurrent.futures import ThreadPoolExecutor
        from etf_terminal.data.ibkr_service import get_ibkr_service
        from etf_terminal.db.database import load_settings

        s = load_settings()
        svc = get_ibkr_service()

        def _do_connect():
            return svc.connect(s.ibkr_host, s.ibkr_port, s.ibkr_client_id)

        import threading
        def _connect_thread():
            ok = _do_connect()
            self.call_from_thread(self._on_ibkr_connected, ok, svc)

        threading.Thread(target=_connect_thread, daemon=True).start()
        self.notify("Connecting to IBKR...")

    def _on_ibkr_connected(self, ok: bool, svc) -> None:
        if ok:
            self._ibkr_connected = True
            self.query_one(StatusBar).refresh()
            self.notify("IBKR connected successfully")
            # Refresh portfolio view if visible
            switcher = self.query_one("#content", ContentSwitcher)
            if switcher.current == "portfolio-overview":
                self.query_one("#portfolio-overview", PortfolioOverviewView)._refresh()
        else:
            err = getattr(svc, '_last_error', 'Unknown error')
            self.notify(f"IBKR connection failed: {err}", severity="error")


def main():
    app = ETFTerminalApp()
    app.run()


if __name__ == "__main__":
    main()
