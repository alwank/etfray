"""ETF Lookthrough view - effective underlying exposure across portfolio."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Static


class LookthroughView(VerticalScroll):
    DEFAULT_CSS = """
    LookthroughView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    LookthroughView DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("ETF Lookthrough — Connect IBKR to view", id="lt-title")
        yield DataTable(id="lt-table")

    def on_mount(self) -> None:
        table = self.query_one("#lt-table", DataTable)
        table.add_columns("Ticker", "Name", "Effective Wt %", "Source ETF")
        table.cursor_type = "row"

    def load_data(self) -> None:
        self.query_one("#lt-table", DataTable).clear()
        self.loading = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from asyncio import to_thread

        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.data.source_resolver import resolve_holdings
        from etfray.domain.portfolio_analytics import calculate_lookthrough

        svc = get_ibkr_service()
        title = self.query_one("#lt-title", Static)
        table = self.query_one("#lt-table", DataTable)
        table.clear()

        if not svc.is_connected or not svc.positions:
            title.update("ETF Lookthrough — IBKR not connected or no positions")
            self.loading = False
            return

        # Calculate portfolio weights
        total_value = sum(abs(p.market_value) for p in svc.positions)
        if total_value == 0:
            title.update("ETF Lookthrough — No position values")
            self.loading = False
            return

        positions = [{"symbol": p.symbol, "weight": abs(p.market_value) / total_value * 100} for p in svc.positions]

        # Get holdings for each ETF using source resolver
        preference = getattr(self.app, "_data_source", "auto")
        holdings_cache = {}
        for pos in positions:
            df, _ = await to_thread(resolve_holdings, pos["symbol"], preference)
            holdings_cache[pos["symbol"]] = df

        lookthrough, unresolved = calculate_lookthrough(positions, holdings_cache)

        resolved_pct = sum(h.total_weight for h in lookthrough)
        unresolved_pct = sum(u.portfolio_weight for u in unresolved)
        title.update(f"ETF Lookthrough — Coverage: {resolved_pct:.0f}% resolved, {unresolved_pct:.0f}% unresolved")

        for h in lookthrough[:100]:
            table.add_row(
                h.ticker,
                h.name,
                f"{h.total_weight:.3f}%",
                ", ".join(h.source_etfs),
            )

        # Show unresolved
        if unresolved:
            table.add_row("", "── Unresolved ETFs ──", "", "")
            for u in unresolved:
                table.add_row(u.ticker, u.reason, f"{u.portfolio_weight:.1f}%", "")

        self.loading = False
