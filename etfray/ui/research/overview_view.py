"""ETF Overview view - high-level snapshot of a selected ETF."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Static


class OverviewView(VerticalScroll):
    DEFAULT_CSS = """
    OverviewView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    OverviewView .title {
        text-style: bold;
        margin-bottom: 1;
    }
    OverviewView .section {
        margin-top: 1;
        border: solid $primary-background;
        padding: 1;
    }
    OverviewView #overview-open-search {
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Select an ETF from Search to view overview.", id="overview-content")
        yield Button("Open Search to select an ETF →", id="overview-open-search", variant="primary")

    def load_etf(self, ticker: str) -> None:
        try:
            self.query_one("#overview-open-search", Button).display = False
        except Exception:
            pass
        self.query_one("#overview-content", Static).update("")
        self.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "overview-open-search":
            self.app.navigate_to("research-search")

    async def _load(self, ticker: str) -> None:
        import asyncio
        from asyncio import to_thread

        from etfray.data.edgar_service import get_etf_report, get_holdings_df
        from etfray.data.market_data_service import get_etf_profile
        from etfray.data.source_resolver import get_freshness_comparison
        from etfray.db.database import load_settings
        from etfray.domain.etf_analytics import calculate_concentration, calculate_exposure
        from etfray.domain.overview_format import format_overview_lines

        content = self.query_one("#overview-content", Static)
        settings = load_settings()

        report, profile, df = await asyncio.gather(
            to_thread(get_etf_report, ticker),
            to_thread(get_etf_profile, ticker),
            to_thread(get_holdings_df, ticker),
        )

        concentration = None
        top_sector = None
        if df is not None and not df.empty:
            concentration = calculate_concentration(df)
            sector_col = "sector" if "sector" in df.columns else None
            if sector_col:
                sectors = calculate_exposure(df, sector_col)
                top_sector = sectors[0] if sectors else None

        freshness_badge = get_freshness_comparison(ticker)
        lines = format_overview_lines(
            ticker,
            report,
            profile,
            concentration,
            top_sector,
            freshness_badge,
            fresh_days=settings.freshness_days_fresh,
            acceptable_days=settings.freshness_days_acceptable,
        )

        self.loading = False
        content.update("\n".join(lines))
