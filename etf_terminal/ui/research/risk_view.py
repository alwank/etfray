"""ETF Risk view - risk category summary derived from holdings data."""

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
        from etf_terminal.data.edgar_service import get_holdings_df
        from etf_terminal.data.source_resolver import get_freshness_comparison
        from etf_terminal.domain.etf_analytics import calculate_concentration

        content = self.query_one("#risk-content", Static)

        df = await to_thread(get_holdings_df, ticker)
        if df is None or df.empty:
            content.loading = False
            content.update(f"Risk — {ticker} (holdings unavailable)")
            return

        conc = calculate_concentration(df)

        # Derive risk categories from holdings data
        has_derivatives = False
        if "is_derivative" in df.columns:
            has_derivatives = df["is_derivative"].any()

        # Concentration risk
        if conc.top10_weight > 50:
            conc_risk = "High"
        elif conc.top10_weight > 30:
            conc_risk = "Medium"
        else:
            conc_risk = "Low"

        # Country concentration
        if "investment_country" in df.columns:
            top_country_pct = float(df.groupby("investment_country")["pct_value"].sum().max())
            country_risk = "High" if top_country_pct > 80 else "Medium" if top_country_pct > 50 else "Low"
        else:
            country_risk = "Unknown"

        # Currency risk
        if "currency_code" in df.columns:
            currencies = df["currency_code"].nunique()
            currency_risk = "Low" if currencies <= 2 else "Medium" if currencies <= 5 else "High"
        else:
            currency_risk = "Unknown"

        badge = get_freshness_comparison(ticker)
        badge_str = f"\n  {badge}" if badge else ""

        lines = [
            f"[bold]Risk Summary — {ticker}[/bold]",
            "",
            f"  Market Risk:         High (equity ETF)",
            f"  Concentration Risk:  {conc_risk} (Top 10: {conc.top10_weight:.1f}%)",
            f"  Country Risk:        {country_risk}",
            f"  Currency Risk:       {currency_risk}",
            f"  Derivatives Risk:    {'Present' if has_derivatives else 'None detected'}",
            f"  Liquidity Risk:      Low (ETF structure)",
            "",
            "── Source ──",
            "  Derived from N-PORT holdings data.",
            "  For full risk disclosures, see prospectus.",
        ]
        if badge_str:
            lines.append(badge_str)
        content.loading = False
        content.update("\n".join(lines))
