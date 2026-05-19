"""Portfolio Concentration view - portfolio-level concentration metrics."""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll


class PortfolioConcentrationView(VerticalScroll):
    DEFAULT_CSS = """
    PortfolioConcentrationView {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Portfolio Concentration — Connect IBKR to view", id="pconc-content")

    def load_data(self) -> None:
        content = self.query_one("#pconc-content", Static)
        content.update("")
        content.loading = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from asyncio import to_thread
        from etf_terminal.data.ibkr_service import get_ibkr_service
        from etf_terminal.data.edgar_service import get_holdings_df
        from etf_terminal.domain.portfolio_analytics import calculate_lookthrough

        svc = get_ibkr_service()
        content = self.query_one("#pconc-content", Static)

        if not svc.is_connected or not svc.positions:
            content.loading = False
            content.update("Portfolio Concentration — IBKR not connected")
            return

        total_value = sum(abs(p.market_value) for p in svc.positions)
        if total_value == 0:
            content.loading = False
            return

        positions = [
            {"symbol": p.symbol, "weight": abs(p.market_value) / total_value * 100}
            for p in svc.positions
        ]

        # ETF-level concentration
        sorted_pos = sorted(positions, key=lambda x: x["weight"], reverse=True)
        top5_etf = sum(p["weight"] for p in sorted_pos[:5])

        # Lookthrough concentration
        holdings_cache = {}
        total = len(positions)
        for i, pos in enumerate(positions):
            content.update(f"Portfolio Concentration — Loading {i + 1}/{total} ETFs...")
            holdings_cache[pos["symbol"]] = await to_thread(get_holdings_df, pos["symbol"])

        lookthrough, unresolved = calculate_lookthrough(positions, holdings_cache)

        top10_lt = sum(h.total_weight for h in lookthrough[:10])
        effective_n = 0
        if lookthrough:
            total_lt = sum(h.total_weight for h in lookthrough)
            if total_lt > 0:
                hhi = sum((h.total_weight / total_lt) ** 2 for h in lookthrough)
                effective_n = 1 / hhi if hhi > 0 else len(lookthrough)

        # Overlap detection
        etf_holdings: dict[str, set] = {}
        for pos in positions:
            df = holdings_cache.get(pos["symbol"])
            if df is not None and not df.empty and "ticker" in df.columns:
                etf_holdings[pos["symbol"]] = set(df["ticker"].dropna().astype(str).str.upper())

        overlap_score = "Low"
        if len(etf_holdings) >= 2:
            symbols = list(etf_holdings.keys())
            overlaps = []
            for i in range(len(symbols)):
                for j in range(i + 1, len(symbols)):
                    s1, s2 = etf_holdings[symbols[i]], etf_holdings[symbols[j]]
                    union = len(s1 | s2)
                    if union:
                        overlaps.append(len(s1 & s2) / union)
            avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
            overlap_score = "High" if avg_overlap > 0.5 else "Medium" if avg_overlap > 0.2 else "Low"

        lines = [
            "[bold]Portfolio Concentration[/bold]",
            "",
            "── ETF Position Level ──",
            f"  Largest ETF:           {sorted_pos[0]['symbol']} ({sorted_pos[0]['weight']:.1f}%)" if sorted_pos else "",
            f"  Top 5 ETF positions:   {top5_etf:.1f}%",
            f"  Number of ETFs:        {len(positions)}",
            "",
            "── Lookthrough Level ──",
            f"  Top 10 effective:      {top10_lt:.2f}%",
            f"  Largest underlying:    {lookthrough[0].ticker} ({lookthrough[0].total_weight:.3f}%)" if lookthrough else "",
            f"  Effective holdings:    {effective_n:.0f}",
            f"  ETF overlap:           {overlap_score}",
            "",
            f"  Unresolved exposure:   {sum(u.portfolio_weight for u in unresolved):.1f}%",
        ]
        content.loading = False
        content.update("\n".join(lines))
