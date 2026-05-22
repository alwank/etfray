"""ETF Exposure view - aggregate holdings into exposure categories."""

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Static


class ExposureView(VerticalScroll):
    DEFAULT_CSS = """
    ExposureView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
    }
    ExposureView Horizontal {
        height: auto;
    }
    ExposureView .exposure-table {
        height: auto;
        width: 1fr;
    }
    """

    _ticker: str = ""
    _sector_data: list = []
    _country_data: list = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Exposure — Select an ETF first", id="exposure-title")
            yield Button("Export", id="export-exposure", variant="success")
        with Horizontal():
            yield DataTable(id="sector-table", classes="exposure-table")
            yield DataTable(id="country-table", classes="exposure-table")

    def on_mount(self) -> None:
        st = self.query_one("#sector-table", DataTable)
        st.add_columns("Sector", "Weight %", "Count")
        st.cursor_type = "row"

        ct = self.query_one("#country-table", DataTable)
        ct.add_columns("Country", "Weight %", "Count")
        ct.cursor_type = "row"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-exposure":
            self._export()

    def load_etf(self, ticker: str) -> None:
        self._ticker = ticker
        self._source_pref = getattr(self.app, "_data_source", "auto")
        self.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread

        from etfray.data.source_resolver import get_freshness_comparison, resolve_holdings
        from etfray.domain.etf_analytics import calculate_exposure

        title = self.query_one("#exposure-title", Static)
        st = self.query_one("#sector-table", DataTable)
        ct = self.query_one("#country-table", DataTable)

        try:
            badge = get_freshness_comparison(ticker)
            badge_str = f" │ {badge}" if badge else ""

            df, source = await to_thread(resolve_holdings, ticker, self._source_pref)

            if df is None or df.empty:
                title.update(f"Exposure — {ticker} (unavailable)")
                return

            title.update(f"Exposure — {ticker} [{source}]{badge_str}")

            # Determine if equity-dominated
            is_equity = True
            if "asset_category" in df.columns:
                value_col = "pct_value" if "pct_value" in df.columns else "value_usd"
                total = df[value_col].abs().sum()
                if total > 0:
                    equity_mask = df["asset_category"].isin(["EC", "EP", ""])
                    equity_pct = df.loc[equity_mask, value_col].abs().sum() / total
                    is_equity = equity_pct > 0.7

            st.clear(columns=True)

            if is_equity and "ticker" in df.columns:
                st.add_columns("Sector", "Weight %", "Count")
                tickers_list = df["ticker"].dropna().astype(str).str.upper().str.strip().tolist()
                tickers_list = [t for t in tickers_list if t]
                from etfray.data.sector_service import get_sectors_bulk
                sector_map = await to_thread(get_sectors_bulk, tickers_list)
                df = df.copy()
                df["sector"] = df["ticker"].apply(
                    lambda t: sector_map.get(str(t).upper().strip(), "Unclassified") if pd.notna(t) and str(t).strip() else "Unclassified"
                )
                self._sector_data = calculate_exposure(df, "sector")
            else:
                st.add_columns("Asset Type", "Weight %", "Count")
                self._sector_data = calculate_exposure(df, "asset_category")

            for e in self._sector_data:
                st.add_row(e.category, f"{e.weight:.1f}%", str(e.count))

            # Country exposure
            self._country_data = calculate_exposure(df, "investment_country") if "investment_country" in df.columns else []
            ct.clear()
            if self._country_data:
                for e in self._country_data:
                    ct.add_row(e.category, f"{e.weight:.1f}%", str(e.count))
            else:
                ct.add_row("N/A — switch to edgar source", "", "")

        except Exception as e:
            title.update(f"Exposure — {ticker} (error: {e})")
        finally:
            self.loading = False

    def _export(self) -> None:
        rows = []
        for e in self._sector_data:
            rows.append({"group": "Asset Type", "category": e.category, "weight_pct": e.weight, "count": e.count})
        for e in self._country_data:
            rows.append({"group": "Country", "category": e.category, "weight_pct": e.weight, "count": e.count})
        if not rows:
            self.app.notify("No data to export", severity="warning")
            return
        df = pd.DataFrame(rows)
        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings
        path = export_dataframe_csv(df, f"{self._ticker}_exposure", load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
