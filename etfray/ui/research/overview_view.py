"""ETF Overview view - high-level snapshot of a selected ETF."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Static, TabbedContent, TabPane


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
        with TabbedContent(id="overview-tabs"):
            with TabPane("Summary", id="tab-summary"):
                yield Static("Select an ETF from Search to view overview.", id="overview-content")
                yield Button("Open Search to select an ETF →", id="overview-open-search", variant="primary")
            with TabPane("Peers", id="tab-peers"):
                yield Static("", id="peers-status")
                yield DataTable(id="peers-table", show_cursor=True)

    def load_etf(self, ticker: str) -> None:
        try:
            self.query_one("#overview-open-search", Button).display = False
        except Exception:
            pass
        self.query_one("#overview-content", Static).update("")
        self.loading = True
        self._current_ticker = ticker
        self.run_worker(self._load(ticker), exclusive=True)
        self.run_worker(self._load_peers(ticker), exclusive=False, name="peers-loader")

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

        report, profile_result, df = await asyncio.gather(
            to_thread(get_etf_report, ticker),
            to_thread(get_etf_profile, ticker),
            to_thread(get_holdings_df, ticker),
        )
        profile, profile_error = profile_result

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
            profile_error=profile_error,
            fresh_days=settings.freshness_days_fresh,
            acceptable_days=settings.freshness_days_acceptable,
        )

        self.loading = False
        content.update("\n".join(lines))

    async def _load_peers(self, ticker: str) -> None:
        import json
        from asyncio import to_thread

        from etfray.data.edgar_service import get_etf_universe
        from etfray.data.market_data_service import ETFProfile
        from etfray.db.database import get_all_cached_profiles, get_cached_etf_profile

        status = self.query_one("#peers-status", Static)
        table = self.query_one("#peers-table", DataTable)

        # Get current ETF's cached profile to determine its category
        current_row = await to_thread(get_cached_etf_profile, ticker)
        if not current_row or not current_row.get("profile_json"):
            status.update("No cached profile for this ETF — open it first to populate.")
            table.display = False
            return

        try:
            current_profile = ETFProfile(**json.loads(current_row["profile_json"]))
        except Exception:
            status.update("Could not parse cached profile for this ETF.")
            table.display = False
            return

        current_category = (current_profile.category or "").strip().lower()
        if not current_category:
            status.update("This ETF has no category — cannot find peers.")
            table.display = False
            return

        # Load universe entries (in-memory cache, fast)
        universe = await to_thread(get_etf_universe)

        # Bulk-fetch all cached profiles in a single DB query, then filter in-memory
        all_profiles_raw = await to_thread(get_all_cached_profiles)
        universe_tickers = {entry.ticker for entry in universe}

        peers: list[tuple[str, ETFProfile]] = []
        for ticker_key, profile_json in all_profiles_raw.items():
            if ticker_key not in universe_tickers:
                continue
            try:
                profile = ETFProfile(**json.loads(profile_json))
            except Exception:
                continue
            if (profile.category or "").strip().lower() == current_category:
                peers.append((ticker_key, profile))

        if len(peers) < 3:
            status.update(
                "No cached peers yet — open ETFs in this category to populate."
            )
            table.display = False
            return

        # Sort by total_assets descending (None sorts last)
        peers.sort(key=lambda t: (t[1].total_assets is None, -(t[1].total_assets or 0)))
        peers = peers[:50]

        # Build table
        status.update("")
        table.display = True

        from etfray.domain.overview_format import fmt_dollars, fmt_expense_ratio, fmt_pct

        if not table.columns:
            table.add_columns(
                "Ticker",
                "Fund Name",
                "Expense Ratio",
                "AUM",
                "YTD%",
                "3Y%",
                "Beta",
                "Holdings",
            )

        table.clear()
        ticker_upper = ticker.upper()
        for t, p in peers:
            ticker_cell = f"{t} ◀" if t.upper() == ticker_upper else t
            fund_name = (p.long_name or p.short_name or "")[:40]
            er = fmt_expense_ratio(p.expense_ratio)
            aum = fmt_dollars(p.total_assets) if p.total_assets is not None else "N/A"
            ytd = fmt_pct(p.ytd_return, signed=True) if p.ytd_return is not None else "N/A"
            ret3y = fmt_pct(p.return_3y, signed=True) if p.return_3y is not None else "N/A"
            beta = f"{p.beta:.2f}" if p.beta is not None else "N/A"
            holdings = "N/A"
            table.add_row(ticker_cell, fund_name, er, aum, ytd, ret3y, beta, holdings)
