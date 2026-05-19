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
            yield DataTable(id="pexp-asset", classes="exp-table")
            yield DataTable(id="pexp-country", classes="exp-table")

    def on_mount(self) -> None:
        self.query_one("#pexp-asset", DataTable).add_columns("Asset Type", "Weight %")
        self.query_one("#pexp-country", DataTable).add_columns("Country", "Weight %")

    def load_data(self) -> None:
        self.query_one("#pexp-title", Static).update("Portfolio Exposure — Loading...")
        asset_table = self.query_one("#pexp-asset", DataTable)
        country_table = self.query_one("#pexp-country", DataTable)
        asset_table.clear()
        country_table.clear()
        asset_table.loading = True
        country_table.loading = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from asyncio import to_thread
        from etf_terminal.data.ibkr_service import get_ibkr_service
        from etf_terminal.data.edgar_service import get_holdings_df
        from etf_terminal.domain.portfolio_analytics import calculate_lookthrough, calculate_portfolio_exposure

        svc = get_ibkr_service()
        title = self.query_one("#pexp-title", Static)

        if not svc.is_connected or not svc.positions:
            title.update("Portfolio Exposure — IBKR not connected")
            self.query_one("#pexp-asset", DataTable).loading = False
            self.query_one("#pexp-country", DataTable).loading = False
            return

        total_value = sum(abs(p.market_value) for p in svc.positions)
        if total_value == 0:
            self.query_one("#pexp-asset", DataTable).loading = False
            self.query_one("#pexp-country", DataTable).loading = False
            return

        positions = [
            {"symbol": p.symbol, "weight": abs(p.market_value) / total_value * 100}
            for p in svc.positions
        ]

        holdings_cache = {}
        total = len(positions)
        for i, pos in enumerate(positions):
            title.update(f"Portfolio Exposure — Loading {i + 1}/{total} ETFs...")
            holdings_cache[pos["symbol"]] = await to_thread(get_holdings_df, pos["symbol"])

        lookthrough, _ = calculate_lookthrough(positions, holdings_cache)

        title.update("Portfolio Exposure")

        # Asset type
        asset_table = self.query_one("#pexp-asset", DataTable)
        asset_table.clear()
        for cat, wt in calculate_portfolio_exposure(lookthrough, "asset_type"):
            asset_table.add_row(cat or "Unclassified", f"{wt:.2f}%")
        asset_table.loading = False

        # Country
        country_table = self.query_one("#pexp-country", DataTable)
        country_table.clear()
        for cat, wt in calculate_portfolio_exposure(lookthrough, "country"):
            country_table.add_row(cat or "Unclassified", f"{wt:.2f}%")
        country_table.loading = False
