"""Watchlist Dashboard - track ETFs with concentration, sector, and overlap metrics."""

from __future__ import annotations

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Input, Static

WATCHLIST_NAME = "default"


class WatchlistView(VerticalScroll):
    DEFAULT_CSS = """
    WatchlistView {
        padding: 1 2;
    }
    WatchlistView Input {
        width: 30;
    }
    WatchlistView DataTable {
        height: 1fr;
    }
    """

    _rows_data: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Static("[bold]Watchlist[/bold]")
        with Horizontal():
            yield Input(placeholder="Add ticker...", id="wl-input")
            yield Button("Remove", id="wl-remove", variant="error")
            yield Button("Refresh", id="wl-refresh")
            yield Button("Export", id="wl-export", variant="success")
        yield DataTable(id="wl-table")

    def on_mount(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        table.add_columns(
            "Ticker", "Fund Name", "Holdings", "Top Holding",
            "Top-10 Wt", "Eff N", "Verdict", "Top Sectors", "Overlap", "Fresh",
        )
        table.cursor_type = "row"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "wl-input" and event.value.strip():
            ticker = event.value.strip().upper()
            from etfray.db.database import add_to_watchlist
            add_to_watchlist(WATCHLIST_NAME, ticker)
            event.input.value = ""
            self.app.notify(f"{ticker} added to watchlist")
            self.load_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wl-remove":
            self._remove_selected()
        elif event.button.id == "wl-refresh":
            self.load_data()
        elif event.button.id == "wl-export":
            self._export()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key:
            self.app.navigate_to_etf(str(event.row_key.value))

    def _remove_selected(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            ticker = str(table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value)
            from etfray.db.database import remove_from_watchlist
            remove_from_watchlist(WATCHLIST_NAME, ticker)
            self.app.notify(f"{ticker} removed from watchlist")
            self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#wl-table", DataTable)
        table.loading = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        from etfray.db.database import get_watchlist

        table = self.query_one("#wl-table", DataTable)
        table.clear()
        self._rows_data = []

        tickers = get_watchlist(WATCHLIST_NAME)
        if not tickers:
            table.loading = False
            return

        preference = getattr(self.app, "_data_source", "auto")

        # Build portfolio df for overlap calculation
        portfolio_df = await self._get_portfolio_df(preference)

        for ticker in tickers:
            row = await self._build_row(ticker, preference, portfolio_df)
            self._rows_data.append(row)
            table.add_row(
                row["ticker"], row["fund_name"], row["holdings"],
                row["top_holding"], row["top10"], row["eff_n"],
                row["verdict"], row["sectors"], row["overlap"], row["fresh"],
                key=ticker,
            )

        table.loading = False

    async def _build_row(self, ticker: str, preference: str, portfolio_df) -> dict:
        from datetime import date, datetime

        from etfray.db.database import get_cached_etf, get_cached_holdings
        from etfray.domain.etf_analytics import (
            calculate_concentration,
            calculate_exposure,
            calculate_weight_overlap,
        )

        row: dict = {
            "ticker": ticker, "fund_name": "", "holdings": "—",
            "top_holding": "—", "top10": "—", "eff_n": "—",
            "verdict": "—", "sectors": "—", "overlap": "—", "fresh": "—",
        }

        # Fund name from cache
        cached_etf = get_cached_etf(ticker)
        if cached_etf:
            row["fund_name"] = cached_etf.fund_name[:25]

        # Use only cached holdings — no network fetch
        cached = get_cached_holdings(ticker)
        if not cached or not cached.get("holdings_json"):
            return row

        import io
        try:
            df = pd.read_json(io.StringIO(cached["holdings_json"]))
        except Exception:
            return row

        if df.empty:
            return row

        # Concentration metrics
        conc = calculate_concentration(df)
        row["holdings"] = f"{conc.num_holdings:,}"
        row["top_holding"] = conc.largest_holding[:15]
        row["top10"] = f"{conc.top10_weight:.1f}%"
        row["eff_n"] = f"{conc.effective_n:.0f}"
        row["verdict"] = conc.verdict[:20]

        # Freshness
        if cached.get("as_of_date"):
            try:
                as_of = datetime.fromisoformat(cached["as_of_date"]).date()
                days = (date.today() - as_of).days
                if days < 60:
                    row["fresh"] = f"🟢 {days}d"
                elif days < 150:
                    row["fresh"] = f"🟡 {days}d"
                else:
                    row["fresh"] = f"🔴 {days}d"
            except (ValueError, TypeError):
                pass

        # Sector exposure (top 3) — use only local sector cache
        if "ticker" in df.columns:
            try:
                from etfray.db.database import get_cached_sectors_bulk
                ticker_list = df["ticker"].dropna().astype(str).str.upper().str.strip().tolist()
                ticker_list = [t for t in ticker_list if t]
                sector_map = get_cached_sectors_bulk(ticker_list)
                if sector_map:
                    df_copy = df.copy()
                    df_copy["sector"] = df_copy["ticker"].apply(
                        lambda t: sector_map.get(str(t).upper().strip(), "Unclassified")
                        if pd.notna(t) and str(t).strip() else "Unclassified"
                    )
                    exposure = calculate_exposure(df_copy, "sector")
                    top3 = [f"{e.category[:4]} {e.weight:.0f}%" for e in exposure[:3]]
                    row["sectors"] = " | ".join(top3)
            except Exception:
                pass

        # Portfolio overlap
        if portfolio_df is not None and not portfolio_df.empty:
            try:
                overlap = calculate_weight_overlap(portfolio_df, df)
                row["overlap"] = f"{overlap:.1f}%"
            except Exception:
                pass

        return row

    async def _get_portfolio_df(self, preference: str):
        """Build a combined holdings DataFrame from IBKR positions using cached data only."""
        import io

        from etfray.data.ibkr_service import get_ibkr_service
        from etfray.db.database import get_cached_holdings

        svc = get_ibkr_service()
        if not svc.is_connected or not svc.positions:
            return None

        total_value = sum(abs(p.market_value) for p in svc.positions)
        if total_value == 0:
            return None

        frames = []
        for p in sorted(svc.positions, key=lambda x: abs(x.market_value), reverse=True)[:5]:
            weight = abs(p.market_value) / total_value
            cached = get_cached_holdings(p.symbol)
            if not cached or not cached.get("holdings_json"):
                continue
            try:
                df = pd.read_json(io.StringIO(cached["holdings_json"]))
                if not df.empty and "ticker" in df.columns and "pct_value" in df.columns:
                    df_copy = df[["ticker", "pct_value"]].copy()
                    df_copy["pct_value"] = df_copy["pct_value"] * weight
                    frames.append(df_copy)
            except Exception:
                continue

        if not frames:
            return None

        combined = pd.concat(frames, ignore_index=True)
        combined = combined.groupby("ticker", as_index=False)["pct_value"].sum()
        return combined

    def _export(self) -> None:
        if not self._rows_data:
            self.app.notify("No data to export", severity="warning")
            return
        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings

        df = pd.DataFrame(self._rows_data)
        path = export_dataframe_csv(df, "watchlist", load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
