"""Margin Dashboard view - IBKR margin and leverage status."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class MarginView(VerticalScroll):
    DEFAULT_CSS = """
    MarginView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Margin Dashboard — Connect IBKR to view", id="margin-content")

    def load_data(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.db.database import load_settings

        svc = get_ibkr_service()
        content = self.query_one("#margin-content", Static)

        if not svc.is_connected or not svc.account_summary:
            content.update("Margin Dashboard — IBKR not connected")
            return

        s = svc.account_summary
        settings = load_settings()

        leverage = s.gross_position_value / s.net_liquidation if s.net_liquidation else 0
        cushion_frac = s.cushion  # always decimal from IBKR
        cushion_pct = cushion_frac * 100  # for display only

        # Stress scenarios
        def stress_cushion(shock_pct: float) -> float:
            """Estimate cushion after a portfolio shock."""
            loss = s.gross_position_value * shock_pct
            new_equity = s.net_liquidation - loss
            if s.maint_margin_req > 0:
                return (new_equity - s.maint_margin_req) / new_equity * 100 if new_equity > 0 else -100
            return 0

        stress_10 = stress_cushion(0.10)
        stress_20 = stress_cushion(0.20)

        # Warnings
        warnings = []
        if cushion_frac < settings.margin_warning_cushion:
            warnings.append("⚠️  Cushion below warning threshold!")
        if leverage > settings.leverage_warning:
            warnings.append("⚠️  Leverage above warning threshold!")
        if s.total_cash_value < 0:
            warnings.append("⚠️  Negative cash balance!")

        lines = [
            "[bold]Margin Dashboard[/bold]",
            "",
            "── Account ──",
            f"  Net Liquidation:       ${s.net_liquidation:,.0f}",
            f"  Gross Position Value:  ${s.gross_position_value:,.0f}",
            f"  Leverage:              {leverage:.2f}x",
            f"  Cash:                  ${s.total_cash_value:,.0f}",
            "",
            "── Margin ──",
            f"  Buying Power:          ${s.buying_power:,.0f}",
            f"  Initial Margin Req:    ${s.init_margin_req:,.0f}",
            f"  Maintenance Margin:    ${s.maint_margin_req:,.0f}",
            f"  Excess Liquidity:      ${s.excess_liquidity:,.0f}",
            f"  Cushion:               {cushion_pct:.1f}%",
            f"  SMA:                   ${s.sma:,.0f}",
            "",
            "── Stress Scenarios ──",
            f"  -10% shock → Cushion:  {stress_10:.1f}%",
            f"  -20% shock → Cushion:  {stress_20:.1f}%",
        ]

        if warnings:
            lines.append("")
            lines.append("── Warnings ──")
            lines.extend(f"  {w}" for w in warnings)

        lines.append(f"\n  Last updated: {s.timestamp}")
        content.update("\n".join(lines))
