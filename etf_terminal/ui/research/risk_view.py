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
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from etf_terminal.data.edgar_service import get_holdings_df
        from etf_terminal.domain.etf_analytics import calculate_concentration

        content = self.query_one("#risk-content", Static)
        content.update(f"Loading risk for {ticker}...")

        df = get_holdings_df(ticker)
        if df is None or df.empty:
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
        content.update("\n".join(lines))
