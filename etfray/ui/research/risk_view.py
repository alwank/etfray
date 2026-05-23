"""ETF Risk view - derived risk metrics + prospectus risk disclosures."""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Static


class RiskView(VerticalScroll):
    DEFAULT_CSS = """
    RiskView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    RiskView #risk-body {
        display: none;
    }
    RiskView #risk-empty Button {
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="risk-empty"):
            yield Static("Risk — Select an ETF first")
            yield Button("Open Search to select an ETF →", id="risk-open-search", variant="primary")
        with Vertical(id="risk-body"):
            yield Static("", id="risk-content")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "risk-open-search":
            self.app.navigate_to("research-search")

    def load_etf(self, ticker: str) -> None:
        self.query_one("#risk-empty").display = False
        self.query_one("#risk-body").display = True
        self.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread

        from etfray.data.edgar_service import get_holdings_df, get_risk_disclosures
        from etfray.data.source_resolver import get_freshness_comparison
        from etfray.domain.etf_analytics import calculate_concentration

        content = self.query_one("#risk-content", Static)

        df = await to_thread(get_holdings_df, ticker)
        if df is None or df.empty:
            self.loading = False
            content.update(f"Risk — {ticker} (holdings unavailable)")
            return

        conc = calculate_concentration(df)

        # Derive risk categories
        has_derivatives = "is_derivative" in df.columns and df["is_derivative"].any()

        conc_risk = "High" if conc.top10_weight > 50 else "Medium" if conc.top10_weight > 30 else "Low"

        country_risk = "Unknown"
        if "investment_country" in df.columns:
            value_col = "pct_value" if "pct_value" in df.columns else "value_usd"
            grouped = df.groupby("investment_country")[value_col].sum()
            total_val = grouped.sum()
            top_country_pct = float(grouped.max() / total_val * 100) if total_val > 0 else 0.0
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
            "  Liquidity Risk:      Low (ETF structure)",
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

        self.loading = False
        content.update("\n".join(lines))
