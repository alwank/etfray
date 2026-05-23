"""ETF Holdings view - sortable DataTable with filters and export."""

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Select, Static


class HoldingsView(VerticalScroll):
    DEFAULT_CSS = """
    HoldingsView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    HoldingsView #holdings-body {
        display: none;
    }
    HoldingsView #holdings-empty Button {
        margin-top: 1;
    }
    HoldingsView #holdings-header {
        height: 3;
    }
    HoldingsView #holdings-filters {
        height: 3;
        margin-bottom: 1;
    }
    HoldingsView #filter-search {
        width: 20;
    }
    HoldingsView #filter-weight {
        width: 12;
    }
    HoldingsView #filter-asset {
        width: 22;
    }
    HoldingsView #filter-country {
        width: 16;
    }
    """

    _top_n: int = 0
    _df: pd.DataFrame | None = None
    _source: str = ""
    _ticker: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="holdings-empty"):
            yield Static("Holdings — Select an ETF first")
            yield Button("Open Search to select an ETF →", id="holdings-open-search", variant="primary")
        with Vertical(id="holdings-body"):
            with Horizontal(id="holdings-header"):
                yield Static("", id="holdings-title")
                yield Button("Top 10", id="top10")
                yield Button("Top 25", id="top25")
                yield Button("All", id="all")
                yield Button("Export", id="export-holdings")
            with Horizontal(id="holdings-filters"):
                yield Input(placeholder="Search...", id="filter-search")
                yield Select([], prompt="Asset Type", id="filter-asset", allow_blank=True)
                yield Select([], prompt="Country", id="filter-country", allow_blank=True)
                yield Input(placeholder="Min wt%", id="filter-weight")
            yield DataTable(id="holdings-table")

    def on_mount(self) -> None:
        table = self.query_one("#holdings-table", DataTable)
        table.cursor_type = "row"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "holdings-open-search":
            self.app.navigate_to("research-search")
            return
        elif event.button.id == "top10":
            self._top_n = 10
        elif event.button.id == "top25":
            self._top_n = 25
        elif event.button.id == "all":
            self._top_n = 0
        elif event.button.id == "export-holdings":
            self._export()
            return
        else:
            return
        self._render_table()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in ("filter-search", "filter-weight"):
            self._render_table()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id in ("filter-asset", "filter-country"):
            self._render_table()

    def load_etf(self, ticker: str) -> None:
        self._ticker = ticker
        self.query_one("#holdings-empty").display = False
        self.query_one("#holdings-body").display = True
        self.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread

        from etfray.data.source_resolver import resolve_holdings

        preference = getattr(self.app, "_data_source", "auto")
        df, source = await to_thread(resolve_holdings, ticker, preference)
        self._df = df
        self._source = source
        self._ticker = ticker

        # Populate filter dropdowns
        if df is not None and not df.empty:
            asset_opts = [("All", "")]
            if "asset_category" in df.columns:
                from etfray.domain.etf_analytics import ASSET_CATEGORY_MAP

                for v in sorted(df["asset_category"].dropna().unique()):
                    label = ASSET_CATEGORY_MAP.get(str(v), str(v)) if v else "Unclassified"
                    asset_opts.append((label, str(v)))
            self.query_one("#filter-asset", Select).set_options(asset_opts)

            country_opts = [("All", "")]
            if "investment_country" in df.columns:
                for v in sorted(df["investment_country"].dropna().unique()):
                    if v:
                        country_opts.append((str(v), str(v)))
            self.query_one("#filter-country", Select).set_options(country_opts)

        self._render_table()
        self.loading = False

    def _get_filtered_df(self) -> pd.DataFrame | None:
        df = self._df
        if df is None or df.empty:
            return df

        sort_col = "pct_value" if "pct_value" in df.columns else "value_usd"
        df = df.sort_values(sort_col, ascending=False)

        # Asset type filter
        asset_val = self.query_one("#filter-asset", Select).value
        if asset_val and asset_val != Select.BLANK and "asset_category" in df.columns:
            df = df[df["asset_category"].astype(str) == asset_val]

        # Country filter
        country_val = self.query_one("#filter-country", Select).value
        if country_val and country_val != Select.BLANK and "investment_country" in df.columns:
            df = df[df["investment_country"].astype(str) == country_val]

        # Weight threshold
        wt_text = self.query_one("#filter-weight", Input).value.strip()
        if wt_text:
            try:
                min_wt = float(wt_text)
                df = df[df[sort_col].astype(float) >= min_wt]
            except ValueError:
                pass

        # Text search
        search_text = self.query_one("#filter-search", Input).value.strip().upper()
        if search_text:
            mask = df.apply(
                lambda r: (
                    search_text in str(r.get("ticker", "")).upper() or search_text in str(r.get("name", "")).upper()
                ),
                axis=1,
            )
            df = df[mask]

        if self._top_n:
            df = df.head(self._top_n)

        return df

    def _render_table(self) -> None:
        title = self.query_one("#holdings-title", Static)
        table = self.query_one("#holdings-table", DataTable)

        df = self._get_filtered_df()
        if df is None or (self._df is not None and self._df.empty):
            title.update(f"Holdings — {self._ticker} (unavailable)")
            return

        is_web = self._source == "web"
        table.clear(columns=True)

        if is_web:
            table.add_columns("Ticker", "Name", "Weight %", "Shares", "52wk Ret %")
        else:
            table.add_columns("Ticker", "Name", "Weight %", "Value", "Shares", "Type", "Country")

        from etfray.db.database import get_cached_holdings

        src_key = "web" if is_web else "nport"
        cached = get_cached_holdings(self._ticker, source=src_key)
        as_of = cached.get("as_of_date", "")[:10] if cached else ""
        shown = len(df) if df is not None else 0
        title.update(f"Holdings — {self._ticker} ({shown:,} shown) │ {self._source.upper()} ({as_of})")

        if df is not None:
            for _, row in df.iterrows():
                pct = float(row.get("pct_value", 0) or 0)
                balance = float(row.get("balance", 0) or 0)
                if is_web:
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

    def _export(self) -> None:
        df = self._get_filtered_df()
        if df is None or df.empty:
            self.app.notify("No data to export", severity="warning")
            return
        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings

        path = export_dataframe_csv(df, f"{self._ticker}_holdings", load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
