"""ETF Holdings view - sortable DataTable using source resolver."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, DataTable, Button
from textual.containers import VerticalScroll


class HoldingsView(VerticalScroll):
    DEFAULT_CSS = """
    HoldingsView {
        padding: 1 2;
    }
    HoldingsView #holdings-header {
        height: 3;
    }
    """

    _top_n: int = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="holdings-header"):
            yield Static("Holdings — Select an ETF first", id="holdings-title")
            yield Button("Top 10", id="top10")
            yield Button("Top 25", id="top25")
            yield Button("All", id="all")
        yield DataTable(id="holdings-table")

    def on_mount(self) -> None:
        table = self.query_one("#holdings-table", DataTable)
        table.cursor_type = "row"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "top10":
            self._top_n = 10
        elif event.button.id == "top25":
            self._top_n = 25
        elif event.button.id == "all":
            self._top_n = 0
        else:
            return
        ticker = getattr(self.app, "_current_etf", None)
        if ticker:
            self.query_one("#holdings-table", DataTable).loading = True
            self.run_worker(self._load(ticker), exclusive=True)

    def load_etf(self, ticker: str) -> None:
        table = self.query_one("#holdings-table", DataTable)
        table.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread
        from etf_terminal.data.source_resolver import resolve_holdings

        title = self.query_one("#holdings-title", Static)
        table = self.query_one("#holdings-table", DataTable)
        title.update(f"Holdings — {ticker}")

        preference = getattr(self.app, "_data_source", "auto")
        df, source = await to_thread(resolve_holdings, ticker, preference)

        if df is None or df.empty:
            title.update(f"Holdings — {ticker} (unavailable)")
            table.loading = False
            return

        df = df.sort_values("pct_value", ascending=False)
        if self._top_n:
            df = df.head(self._top_n)

        # Rebuild columns based on source
        table.clear(columns=True)
        is_zacks = source == "zacks"

        if is_zacks:
            table.add_columns("Ticker", "Name", "Weight %", "Shares", "52wk Ret %")
        else:
            table.add_columns("Ticker", "Name", "Weight %", "Value", "Shares", "Type", "Country")

        from etf_terminal.db.database import get_cached_holdings
        src_key = "zacks" if is_zacks else "nport"
        cached = get_cached_holdings(ticker, source=src_key)
        as_of = cached.get("as_of_date", "")[:10] if cached else ""
        title.update(f"Holdings — {ticker} ({len(df):,} shown) │ {source.upper()} ({as_of})")

        for _, row in df.iterrows():
            pct = float(row.get("pct_value", 0) or 0)
            balance = float(row.get("balance", 0) or 0)
            if is_zacks:
                w52 = float(row.get("week52_return", 0) or 0)
                table.add_row(
                    str(row.get("ticker", "") or ""),
                    str(row.get("name", "") or "")[:30],
                    f"{pct:.2f}%" if pct else "—",
                    f"{balance:,.0f}" if balance else "—",
                    f"{w52:.2f}%" if w52 else "—",
                )
            else:
                value = float(row.get("value_usd", 0) or 0)
                table.add_row(
                    str(row.get("ticker", "") or ""),
                    str(row.get("name", "") or "")[:30],
                    f"{pct:.2f}%" if pct else "—",
                    f"${value:,.0f}" if value else "—",
                    f"{balance:,.0f}" if balance else "—",
                    str(row.get("asset_category", "") or ""),
                    str(row.get("investment_country", "") or ""),
                )

        table.loading = False
