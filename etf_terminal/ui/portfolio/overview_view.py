"""Portfolio Overview view - IBKR account summary at a glance."""

from textual.app import ComposeResult
from textual.widgets import Static, Button
from textual.containers import Horizontal
from textual.containers import VerticalScroll


class PortfolioOverviewView(VerticalScroll):
    DEFAULT_CSS = """
    PortfolioOverviewView {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("[bold]Portfolio Overview[/bold]", id="port-title")
            yield Button("Connect IBKR", id="btn-connect")
            yield Button("Refresh", id="btn-refresh")
        yield Static("IBKR not connected. Configure in Settings and connect.", id="port-content")

    def on_mount(self) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-connect":
            self.run_worker(self._connect(), exclusive=True)
        elif event.button.id == "btn-refresh":
            self.run_worker(self._do_refresh(), exclusive=True)

    async def _connect(self) -> None:
        from etf_terminal.data.ibkr_service import get_ibkr_service
        from etf_terminal.db.database import load_settings

        s = load_settings()
        svc = get_ibkr_service()
        ok = svc.connect(s.ibkr_host, s.ibkr_port, s.ibkr_client_id)
        if ok:
            self.app._ibkr_connected = True
            self.app.query_one("StatusBar").refresh()
            self._refresh()
        else:
            self.query_one("#port-content", Static).update(
                "Failed to connect to IBKR.\nEnsure TWS/Gateway is running and API is enabled."
            )

    async def _do_refresh(self) -> None:
        from etf_terminal.data.ibkr_service import get_ibkr_service
        svc = get_ibkr_service()
        svc.refresh()
        self._refresh()

    def _refresh(self) -> None:
        from etf_terminal.data.ibkr_service import get_ibkr_service

        svc = get_ibkr_service()
        if not svc.is_connected:
            return

        s = svc.account_summary
        if not s:
            return

        leverage = s.gross_position_value / s.net_liquidation if s.net_liquidation else 0
        cushion_pct = s.cushion * 100 if s.cushion < 1 else s.cushion

        lines = [
            "[bold]Portfolio Overview[/bold]                    IBKR: Connected",
            "",
            "── Account Summary ──",
            f"  Net Liquidation:     ${s.net_liquidation:,.0f}",
            f"  Gross Exposure:      ${s.gross_position_value:,.0f}",
            f"  Leverage:            {leverage:.2f}x",
            f"  Cash:                ${s.total_cash_value:,.0f}",
            f"  Cushion:             {cushion_pct:.1f}%",
            "",
            "── Margin ──",
            f"  Buying Power:        ${s.buying_power:,.0f}",
            f"  Initial Margin:      ${s.init_margin_req:,.0f}",
            f"  Maintenance Margin:  ${s.maint_margin_req:,.0f}",
            f"  Excess Liquidity:    ${s.excess_liquidity:,.0f}",
            f"  SMA:                 ${s.sma:,.0f}",
            "",
            f"  Last updated: {s.timestamp}",
        ]

        # Warnings
        from etf_terminal.db.database import load_settings
        settings = load_settings()
        if cushion_pct / 100 < settings.margin_warning_cushion:
            lines.append("\n⚠️  WARNING: Margin cushion below threshold!")
        if leverage > settings.leverage_warning:
            lines.append("⚠️  WARNING: Leverage above threshold!")

        self.query_one("#port-content", Static).update("\n".join(lines))
