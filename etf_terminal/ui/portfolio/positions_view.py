"""Portfolio Positions view - IBKR positions table."""

from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from textual.containers import VerticalScroll


class PositionsView(VerticalScroll):
    DEFAULT_CSS = """
    PositionsView {
        padding: 1 2;
    }
    PositionsView DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Positions", id="pos-title")
        yield DataTable(id="pos-table")

    def on_mount(self) -> None:
        table = self.query_one("#pos-table", DataTable)
        table.add_columns("Symbol", "Qty", "Avg Cost", "Mkt Value", "Weight %", "P&L", "Currency")
        table.cursor_type = "row"
        self._refresh()

    def _refresh(self) -> None:
        from etf_terminal.data.ibkr_service import get_ibkr_service

        svc = get_ibkr_service()
        table = self.query_one("#pos-table", DataTable)
        title = self.query_one("#pos-title", Static)
        table.clear()

        if not svc.is_connected:
            title.update("Positions — IBKR not connected")
            return

        positions = svc.positions
        if not positions:
            title.update("Positions — No positions found")
            return

        # Calculate total market value for weights
        total_value = sum(abs(p.market_value) for p in positions)

        title.update(f"Positions ({len(positions)})")
        for p in sorted(positions, key=lambda x: abs(x.market_value), reverse=True):
            weight = (abs(p.market_value) / total_value * 100) if total_value else 0
            pnl = p.unrealized_pnl
            table.add_row(
                p.symbol,
                f"{p.quantity:,.0f}",
                f"${p.avg_cost:,.2f}",
                f"${p.market_value:,.0f}",
                f"{weight:.1f}%",
                f"${pnl:+,.0f}" if pnl else "—",
                p.currency,
                key=p.symbol,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open ETF research for selected position."""
        if event.row_key:
            symbol = str(event.row_key.value)
            self.app.navigate_to_etf(symbol)
