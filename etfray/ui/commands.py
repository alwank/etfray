"""Command palette providers for ETF Terminal."""

from __future__ import annotations

from textual.command import Hit, Hits, Provider


class ETFCommands(Provider):
    """Command palette provider for ETF Terminal navigation and actions."""

    async def search(self, query: str) -> Hits:
        app = self.app
        matcher = self.matcher(query)

        commands = [
            ("Search ETFs", "research-search"),
            ("ETF Overview", "research-overview"),
            ("ETF Holdings", "research-holdings"),
            ("ETF Exposure", "research-exposure"),
            ("ETF Concentration", "research-concentration"),
            ("ETF Fees", "research-fees"),
            ("ETF Risk", "research-risk"),
            ("ETF Documents", "research-documents"),
            ("Compare ETFs", "research-compare"),
            ("Portfolio Overview", "portfolio-overview"),
            ("Portfolio Positions", "portfolio-positions"),
            ("ETF Lookthrough", "portfolio-lookthrough"),
            ("Portfolio Exposure", "portfolio-exposure"),
            ("Portfolio Concentration", "portfolio-concentration"),
            ("Margin Dashboard", "portfolio-margin"),
            ("Portfolio Risk", "portfolio-risk"),

            ("Exports", "workspace-exports"),
            ("Watchlist", "workspace-watchlist"),
            ("Settings", "workspace-settings"),
        ]

        for label, view_id in commands:
            score = matcher.match(label)
            if score > 0:
                yield Hit(score, label, lambda v=view_id: app.navigate_to(v), label)

        # "open TICKER" command
        if query.lower().startswith("open "):
            ticker = query[5:].strip().upper()
            if ticker:
                yield Hit(
                    100,
                    f"Open {ticker}",
                    lambda t=ticker: app.navigate_to_etf(t),
                    f"Open ETF: {ticker}",
                )

        # "compare TICKER TICKER" command
        if query.lower().startswith("compare "):
            tickers = query[8:].strip().upper()
            if tickers:
                yield Hit(
                    100,
                    f"Compare {tickers}",
                    lambda: app.navigate_to("research-compare"),
                    f"Compare ETFs: {tickers}",
                )
