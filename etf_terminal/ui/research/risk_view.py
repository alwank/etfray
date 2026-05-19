"""ETF Risk view - derived risk metrics + prospectus risk disclosures."""

from textual.app import ComposeResult
from textual.widgets import Static
from textual.containers import VerticalScroll


class RiskView(VerticalScroll):
    DEFAULT_CSS = """
    RiskView {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Risk — Select an ETF first", id="risk-content")

    def load_etf(self, ticker: str) -> None:
        content = self.query_one("#risk-content", Static)
        content.update("")
        content.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread
        from etf_terminal.data.edgar_service import get_holdings_df, get_risk_disclosures
        from etf_terminal.data.source_resolver import get_freshness_comparison
        from etf_terminal.domain.etf_analytics import calculate_concentration

        content = self.query_one("#risk-content", Static)

        df = await to_thread(get_holdings_df, ticker)
        if df is None or df.empty:
            content.loading = False
            content.update(f"Risk — {ticker} (holdings unavailable)")
            return

        conc = calculate_concentration(df)

        # Derive risk categories
        has_derivatives = "is_derivative" in df.columns and df["is_derivative"].any()

        conc_risk = "High" if conc.top10_weight > 50 else "Medium" if conc.top10_weight > 30 else "Low"

        country_risk = "Unknown"
        if "investment_country" in df.columns:
            top_country_pct = float(df.groupby("investment_country")["pct_value"].sum().max())
            country_risk = "High" if top_country_pct > 80 else "Medium" if top_country_pct > 50 else "Low"

        currency_risk = "Unknown"
        if "currency_code" in df.columns:
            currencies = df["currency_code"].nunique()
            currency_risk = "Low" if currencies <= 2 else "Medium" if currencies <= 5 else "High"

        badge = get_freshness_comparison(ticker)
        lines = [
            f"[bold]Risk Summary — {ticker}[/bold]",
            "",
            f"  Concentration Risk:  {conc_risk} (Top 10: {conc.top10_weight:.1f}%)",
            f"  Country Risk:        {country_risk}",
            f"  Currency Risk:       {currency_risk}",
            f"  Derivatives:         {'Present' if has_derivatives else 'None detected'}",
            f"  Liquidity Risk:      Low (ETF structure)",
        ]
        if badge:
            lines.append(f"  {badge}")

        # Prospectus risk disclosures
        lines.append("")
        lines.append("── Prospectus Risk Disclosures ──")

        disclosures = await to_thread(get_risk_disclosures, ticker)
        if disclosures:
            lines.append(f"  Source: {disclosures[0].source_form} filed {disclosures[0].filed_date}")
            lines.append("")
            for d in disclosures:
                lines.append(f"  • {d.title}")
                if d.summary:
                    lines.append(f"    {d.summary[:120]}...")
        else:
            lines.append("  Prospectus risk disclosures unavailable.")
            lines.append("  Check Documents view for latest N-1A or 497 filing.")

        content.loading = False
        content.update("\n".join(lines))
