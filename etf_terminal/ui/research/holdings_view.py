"""ETF Holdings view - sortable DataTable of fund holdings."""

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
    HoldingsView DataTable {
        height: 1fr;
    }
    """

    _top_n: int = 0  # 0 = all

    def compose(self) -> ComposeResult:
        with Horizontal(id="holdings-header"):
            yield Static("Holdings — Select an ETF first", id="holdings-title")
            yield Button("Top 10", id="top10")
            yield Button("Top 25", id="top25")
            yield Button("All", id="all")
        yield DataTable(id="holdings-table")

    def on_mount(self) -> None:
        table = self.query_one("#holdings-table", DataTable)
        table.add_columns("Ticker", "Name", "Weight %", "Value", "Shares", "Type", "Country")
        table.cursor_type = "row"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "top10":
            self._top_n = 10
        elif event.button.id == "top25":
            self._top_n = 25
        else:
            self._top_n = 0
        ticker = getattr(self.app, "_current_etf", None)
        if ticker:
            self.load_etf(ticker)

    def load_etf(self, ticker: str) -> None:
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from etf_terminal.data.edgar_service import get_holdings_df

        table = self.query_one("#holdings-table", DataTable)
        title = self.query_one("#holdings-title", Static)
        table.clear()

        title.update(f"Holdings — {ticker} (loading...)")
        df = get_holdings_df(ticker)

        if df is None or df.empty:
            title.update(f"Holdings — {ticker} (unavailable)")
            return

        # Sort by weight/value
        sort_col = "pct_value" if "pct_value" in df.columns else "value_usd"
        df = df.sort_values(sort_col, ascending=False)

        if self._top_n:
            df = df.head(self._top_n)

        count = len(df)

        # Show source
        from etf_terminal.db.database import get_cached_holdings
        cached = get_cached_holdings(ticker)
        source = "Issuer daily" if cached and cached.get("source") == "issuer" else "N-PORT"
        as_of = cached.get("as_of_date", "") if cached else ""
        title.update(f"Holdings — {ticker} ({count:,} shown) │ Source: {source} ({as_of})")

        for _, row in df.iterrows():
            ticker_val = str(row.get("ticker", "") or "")
            name = str(row.get("name", "") or "")[:30]
            pct = float(row.get("pct_value", 0) or 0)
            value = float(row.get("value_usd", 0) or 0)
            balance = float(row.get("balance", 0) or 0)
            asset_cat = str(row.get("asset_category", "") or "")
            country = str(row.get("investment_country", "") or "")

            pct_str = f"{pct:.2f}%" if pct else "—"
            val_str = f"${value:,.0f}" if value else "—"
            bal_str = f"{balance:,.0f}" if balance else "—"

            table.add_row(ticker_val, name, pct_str, val_str, bal_str, asset_cat, country)
