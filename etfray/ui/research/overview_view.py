"""ETF Overview view - high-level snapshot of a selected ETF."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, Static, TabbedContent, TabPane

# Skip live enrichment when the cache already has this many category peers.
_MIN_PEERS_BEFORE_ENRICHMENT = 15
# Maximum number of confirmed-match Yahoo fetches per enrichment run.
_MAX_LIVE_PEER_FETCHES = 10
# Maximum total Yahoo fetch attempts per enrichment run (includes non-matching fetches).
_MAX_LIVE_PEER_ATTEMPTS = 15


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
        yield Static("Select an ETF from Search to view overview.", id="overview-placeholder")
        yield Button("Open Search to select an ETF →", id="overview-open-search", variant="primary")
        with TabbedContent(id="overview-tabs"):
            with TabPane("Summary", id="tab-summary"):
                yield Static("", id="overview-content")
            with TabPane("Peers", id="tab-peers"):
                yield Static("", id="peers-status")
                yield DataTable(id="peers-table", show_cursor=True)

    def on_mount(self) -> None:
        self.query_one("#overview-tabs", TabbedContent).display = False

    def load_etf(self, ticker: str) -> None:
        self.query_one("#overview-placeholder", Static).display = False
        self.query_one("#overview-open-search", Button).display = False
        self.query_one("#overview-tabs", TabbedContent).display = True
        self.loading = True
        self._current_ticker = ticker
        # Show a holding message on the peers tab while _load() fetches the profile.
        self.query_one("#peers-status", Static).update("Loading profile…")
        self.query_one("#peers-table", DataTable).display = False
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

        # Guard against EDGAR calls that iterate 150+ N-PORT XML downloads (e.g. large
        # fund families like ProShares/iShares).  Profile is excluded — it uses yfinance
        # which has its own retry logic and is typically fast on cache hit.
        _EDGAR_TIMEOUT = 25.0

        async def _edgar_task(coro, default):
            try:
                return await asyncio.wait_for(coro, timeout=_EDGAR_TIMEOUT)
            except asyncio.TimeoutError:
                return default

        report, profile_result, df = await asyncio.gather(
            _edgar_task(to_thread(get_etf_report, ticker), None),
            to_thread(get_etf_profile, ticker),
            _edgar_task(to_thread(get_holdings_df, ticker), None),
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

        # Launch peers now that the profile is already in memory — avoids a
        # second concurrent Yahoo fetch which causes the summary gather to hang.
        if profile is not None and getattr(self, "_current_ticker", None) == ticker:
            self.run_worker(
                self._load_peers(ticker, profile),
                exclusive=False,
                name="peers-loader",
            )
        elif profile is None:
            self.query_one("#peers-status", Static).update(
                f"Could not load profile: {profile_error}" if profile_error
                else "Could not load profile for this ETF."
            )

    # ------------------------------------------------------------------
    # Peers tab helpers
    # ------------------------------------------------------------------

    def _ensure_peers_columns(self, table: DataTable) -> None:
        """Add column headers to the peers table if not already present."""
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

    def _peer_row(self, ticker_key: str, p: object, current_ticker: str) -> tuple:  # type: ignore[type-arg]
        """Build a row tuple for the peers DataTable from an ETFProfile."""
        from etfray.domain.overview_format import fmt_dollars, fmt_expense_ratio, fmt_pct

        ticker_cell = f"{ticker_key} ◀" if ticker_key.upper() == current_ticker.upper() else ticker_key
        fund_name = (getattr(p, "long_name", "") or getattr(p, "short_name", "") or "")[:40]
        er = fmt_expense_ratio(getattr(p, "expense_ratio", None))
        aum = fmt_dollars(p.total_assets) if getattr(p, "total_assets", None) is not None else "N/A"
        ytd = fmt_pct(p.ytd_return, signed=True) if getattr(p, "ytd_return", None) is not None else "N/A"
        ret3y = fmt_pct(p.return_3y, signed=True) if getattr(p, "return_3y", None) is not None else "N/A"
        beta = f"{p.beta:.2f}" if getattr(p, "beta", None) is not None else "N/A"
        return (ticker_cell, fund_name, er, aum, ytd, ret3y, beta, "N/A")

    # ------------------------------------------------------------------
    # Tier-1: render cached peers
    # ------------------------------------------------------------------

    async def _load_peers(self, ticker: str, current_profile: object) -> None:
        import json
        from asyncio import to_thread

        from etfray.data.edgar_service import get_etf_universe
        from etfray.data.market_data_service import ETFProfile
        from etfray.db.database import get_all_cached_profiles

        status = self.query_one("#peers-status", Static)
        table = self.query_one("#peers-table", DataTable)

        # Profile is passed in directly from _load() — no separate Yahoo fetch needed.
        current_category = (getattr(current_profile, "category", "") or "").strip().lower()
        if not current_category:
            status.update("This ETF has no category — cannot find peers.")
            table.display = False
            return

        # Load universe entries (in-memory cache, fast)
        universe = await to_thread(get_etf_universe)

        # Bulk-fetch all cached profiles in a single DB query, then filter in-memory.
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

        # Sort by total_assets descending (None sorts last), cap at 50.
        peers.sort(key=lambda t: (t[1].total_assets is None, -(t[1].total_assets or 0)))
        peers = peers[:50]

        if peers:
            self._ensure_peers_columns(table)
            table.clear()
            table.display = True
            for t, p in peers:
                table.add_row(*self._peer_row(t, p, ticker))

        # Launch tier-2 enrichment when we don't have enough cached peers yet.
        if len(peers) < _MIN_PEERS_BEFORE_ENRICHMENT:
            if not peers:
                status.update("No cached peers yet — searching Yahoo for peers…")
            self.run_worker(
                self._enrich_peers(ticker, current_category, len(peers)),
                exclusive=False,
                name="peers-enricher",
            )
        else:
            status.update("")

    # ------------------------------------------------------------------
    # Tier-2: live enrichment from Yahoo
    # ------------------------------------------------------------------

    async def _enrich_peers(
        self, ticker: str, current_category: str, existing_count: int
    ) -> None:
        """Fetch profiles for universe candidates not yet in the cache and add them live."""
        from asyncio import to_thread

        from etfray.data.edgar_service import get_etf_universe
        from etfray.data.market_data_service import get_etf_profile, get_peer_candidates
        from etfray.db.database import get_all_cached_profiles

        status = self.query_one("#peers-status", Static)
        table = self.query_one("#peers-table", DataTable)

        universe = await to_thread(get_etf_universe)
        all_profiles_raw = await to_thread(get_all_cached_profiles)
        cached_tickers = set(all_profiles_raw.keys())

        candidates = get_peer_candidates(
            current_category,
            universe,
            cached_tickers,
            max_candidates=_MAX_LIVE_PEER_FETCHES * 5,
        )

        fetched_count = 0
        _attempt_count = 0
        for candidate in candidates:
            if fetched_count >= _MAX_LIVE_PEER_FETCHES:
                break
            if _attempt_count >= _MAX_LIVE_PEER_ATTEMPTS:
                break

            # Abort if the user has navigated to a different ticker.
            if getattr(self, "_current_ticker", None) != ticker:
                return

            status.update(
                f"Fetching peers from Yahoo… ({fetched_count}/{_MAX_LIVE_PEER_FETCHES})"
            )

            profile, _ = await to_thread(get_etf_profile, candidate.ticker)
            _attempt_count += 1

            if profile is None:
                continue

            # Confirm Yahoo's actual category matches — discard false positives.
            if (profile.category or "").strip().lower() != current_category:
                continue

            self._ensure_peers_columns(table)
            table.display = True
            table.add_row(*self._peer_row(candidate.ticker, profile, ticker))
            fetched_count += 1

        total = existing_count + fetched_count
        if fetched_count > 0:
            status.update(f"Showing {total} peer(s) · {fetched_count} fetched live from Yahoo")
        else:
            status.update("" if existing_count > 0 else "No peers found in this category.")
