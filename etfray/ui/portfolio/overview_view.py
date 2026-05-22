"""Portfolio Overview view - IBKR account summary at a glance."""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static


class PortfolioOverviewView(VerticalScroll):
    DEFAULT_CSS = """
    PortfolioOverviewView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    PortfolioOverviewView #port-toolbar {
        height: 3;
        width: 100%;
    }
    PortfolioOverviewView Button {
        min-width: 16;
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="port-toolbar"):
            yield Button("Connect IBKR", id="btn-connect", variant="primary")
            yield Button("Refresh", id="btn-refresh")
        yield Static("IBKR not connected. Configure in Settings and connect.", id="port-content")

    def on_mount(self) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-connect":
            self._do_connect_thread()
        elif event.button.id == "btn-refresh":
            self._do_refresh_thread()

    def _do_connect_thread(self) -> None:
        import threading

        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.db.database import load_settings

        s = load_settings()
        svc = get_ibkr_service()

        def _connect():
            ok = svc.connect(s.ibkr_host, s.ibkr_port, s.ibkr_client_id)
            self.app.call_from_thread(self._on_connected, ok, svc)

        self.query_one("#port-content", Static).update("")
        self.loading = True
        threading.Thread(target=_connect, daemon=True).start()

    def _on_connected(self, ok: bool, svc) -> None:
        self.loading = False
        if ok:
            self.app._ibkr_connected = True
            self.app.query_one("StatusBar").refresh()
            self._refresh()
        else:
            err = getattr(svc, '_last_error', 'Unknown error')
            self.query_one("#port-content", Static).update(
                f"Failed to connect to IBKR.\n{err}\n\n"
                "Ensure TWS/Gateway is running and API is enabled."
            )

    def _do_refresh_thread(self) -> None:
        import threading

        from etfray.data.ibkr_service import get_ibkr_service

        svc = get_ibkr_service()
        self.loading = True

        def _work():
            svc.refresh()
            self.app.call_from_thread(self._on_refresh_done)

        threading.Thread(target=_work, daemon=True).start()

    def _on_refresh_done(self) -> None:
        self.loading = False
        self._refresh()

    def _refresh(self) -> None:
        from etfray.data.ibkr_service import get_ibkr_service

        svc = get_ibkr_service()
        btn_connect = self.query_one("#btn-connect", Button)
        btn_refresh = self.query_one("#btn-refresh", Button)
        if not svc.is_connected:
            btn_connect.display = True
            btn_refresh.display = False
            return
        btn_connect.display = False
        btn_refresh.display = True

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
        from etfray.db.database import load_settings
        settings = load_settings()
        if cushion_pct / 100 < settings.margin_warning_cushion:
            lines.append("\n⚠️  WARNING: Margin cushion below threshold!")
        if leverage > settings.leverage_warning:
            lines.append("⚠️  WARNING: Leverage above threshold!")

        self.query_one("#port-content", Static).update("\n".join(lines))
