"""Portfolio Exposure view - aggregated exposure across all positions."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, DataTable
from textual.containers import VerticalScroll


class PortfolioExposureView(VerticalScroll):
    DEFAULT_CSS = """
    PortfolioExposureView {
        padding: 1 2;
    }
    PortfolioExposureView Horizontal {
        height: auto;
    }
    PortfolioExposureView .exp-table {
        height: auto;
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Portfolio Exposure — Connect IBKR to view", id="pexp-title")
        with Horizontal():
            yield DataTable(id="pexp-sector", classes="exp-table")
            yield DataTable(id="pexp-country", classes="exp-table")

    def on_mount(self) -> None:
        self.query_one("#pexp-sector", DataTable).add_columns("Sector", "Weight %")
        self.query_one("#pexp-country", DataTable).add_columns("Country", "Weight %")

    def load_data(self) -> None:
        self.query_one("#pexp-title", Static).update("Portfolio Exposure — Loading...")
        sector_table = self.query_one("#pexp-sector", DataTable)
        country_table = self.query_one("#pexp-country", DataTable)
        sector_table.clear()
        country_table.clear()
        sector_table.loading = True
        country_table.loading = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from asyncio import to_thread
        from etf_terminal.data.ibkr_service import get_ibkr_service
        from etf_terminal.data.source_resolver import resolve_holdings
        from etf_terminal.domain.portfolio_analytics import calculate_lookthrough, calculate_portfolio_exposure
        from etf_terminal.data.sector_service import get_sectors_bulk

        svc = get_ibkr_service()
        title = self.query_one("#pexp-title", Static)

        if not svc.is_connected or not svc.positions:
            title.update("Portfolio Exposure — IBKR not connected")
            self.query_one("#pexp-sector", DataTable).loading = False
            self.query_one("#pexp-country", DataTable).loading = False
            return

        total_value = sum(abs(p.market_value) for p in svc.positions)
        if total_value == 0:
            self.query_one("#pexp-sector", DataTable).loading = False
            self.query_one("#pexp-country", DataTable).loading = False
            return

        positions = [
            {"symbol": p.symbol, "weight": abs(p.market_value) / total_value * 100}
            for p in svc.positions
        ]

        holdings_cache = {}
        total = len(positions)
        preference = getattr(self.app, "_data_source", "auto")
        for i, pos in enumerate(positions):
            title.update(f"Portfolio Exposure — Loading {i + 1}/{total} ETFs...")
            df, _ = await to_thread(resolve_holdings, pos["symbol"], preference)
            holdings_cache[pos["symbol"]] = df

        lookthrough, _ = calculate_lookthrough(positions, holdings_cache)

        # Populate sector for all lookthrough holdings
        tickers = [h.ticker for h in lookthrough if h.ticker]
        sector_map = await to_thread(get_sectors_bulk, tickers)
        for h in lookthrough:
            if h.ticker and h.ticker in sector_map:
                h.sector = sector_map[h.ticker]

        title.update("Portfolio Exposure")

        # Sector
        sector_table = self.query_one("#pexp-sector", DataTable)
        sector_table.clear()
        for cat, wt in calculate_portfolio_exposure(lookthrough, "sector"):
            sector_table.add_row(cat or "Unclassified", f"{wt:.2f}%")
        sector_table.loading = False

        # Country
        country_table = self.query_one("#pexp-country", DataTable)
        country_table.clear()
        for cat, wt in calculate_portfolio_exposure(lookthrough, "country"):
            country_table.add_row(cat or "Unclassified", f"{wt:.2f}%")
        country_table.loading = False
