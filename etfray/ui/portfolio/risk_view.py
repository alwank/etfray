"""Portfolio Risk view - combined risk summary from IBKR + EDGAR data."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


class PortfolioRiskView(VerticalScroll):
    DEFAULT_CSS = """
    PortfolioRiskView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Portfolio Risk — Connect IBKR to view", id="prisk-content")

    def load_data(self) -> None:
        self.query_one("#prisk-content", Static).update("")
        self.loading = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from asyncio import to_thread

        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.data.source_resolver import resolve_holdings
        from etfray.domain.portfolio_analytics import calculate_lookthrough, calculate_portfolio_exposure

        svc = get_ibkr_service()
        content = self.query_one("#prisk-content", Static)

        if not svc.is_connected or not svc.account_summary:
            self.loading = False
            content.update("Portfolio Risk — IBKR not connected")
            return

        s = svc.account_summary
        leverage = s.gross_position_value / s.net_liquidation if s.net_liquidation else 0
        cushion_pct = s.cushion * 100 if s.cushion < 1 else s.cushion

        # Leverage risk
        if leverage > 2.0:
            leverage_risk = "High"
        elif leverage > 1.5:
            leverage_risk = "Medium"
        else:
            leverage_risk = "Low"

        # Margin risk
        if cushion_pct < 10:
            margin_risk = "High"
        elif cushion_pct < 20:
            margin_risk = "Medium"
        else:
            margin_risk = "Low"

        # Lookthrough-based risks
        equity_pct = 0.0
        top10_pct = 0.0
        data_coverage = "Unknown"

        if svc.positions:
            total_value = sum(abs(p.market_value) for p in svc.positions)
            if total_value > 0:
                positions = [
                    {"symbol": p.symbol, "weight": abs(p.market_value) / total_value * 100} for p in svc.positions
                ]

                holdings_cache = {}
                resolved_count = 0
                preference = getattr(self.app, "_data_source", "auto")
                for pos in positions:
                    df, _ = await to_thread(resolve_holdings, pos["symbol"], preference)
                    holdings_cache[pos["symbol"]] = df
                    if df is not None and not df.empty:
                        resolved_count += 1

                lookthrough, unresolved = calculate_lookthrough(positions, holdings_cache)

                # Equity exposure
                for cat, wt in calculate_portfolio_exposure(lookthrough, "asset_type"):
                    if "EC" in cat or "Equity" in cat:
                        equity_pct += wt

                # Concentration
                top10_pct = sum(h.total_weight for h in lookthrough[:10])

                # Data coverage: how many positions have resolved holdings
                total_pos = len(positions)
                if resolved_count == total_pos:
                    data_coverage = "Full"
                elif resolved_count > total_pos * 0.5:
                    data_coverage = "Partial"
                else:
                    data_coverage = "Low"

        # Concentration risk
        if top10_pct > 30:
            conc_risk = "High"
        elif top10_pct > 15:
            conc_risk = "Medium"
        else:
            conc_risk = "Low"

        lines = [
            "[bold]Portfolio Risk Summary[/bold]",
            "",
            f"  Leverage Risk:         {leverage_risk} ({leverage:.2f}x)",
            f"  Margin Risk:           {margin_risk} (cushion: {cushion_pct:.1f}%)",
            f"  Equity Exposure:       {equity_pct:.1f}%",
            f"  Concentration Risk:    {conc_risk} (top 10: {top10_pct:.2f}%)",
            f"  Data Coverage:         {data_coverage}",
            "",
            "── Risk Drivers ──",
        ]

        if leverage_risk != "Low":
            lines.append(f"  • Leverage at {leverage:.2f}x increases margin call risk")
        if margin_risk != "Low":
            lines.append(f"  • Cushion at {cushion_pct:.1f}% — limited buffer")
        if equity_pct > 80:
            lines.append(f"  • High equity concentration ({equity_pct:.0f}%)")
        if data_coverage == "Low":
            lines.append("  • Holdings data may be outdated")
        if not any(r != "Low" for r in [leverage_risk, margin_risk]):
            lines.append("  • No significant risk drivers detected")

        lines.append("\n  Source: IBKR account + EDGAR holdings data")
        self.loading = False
        content.update("\n".join(lines))
