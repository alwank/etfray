"""ETF Compare view - side-by-side comparison of 2-5 ETFs."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, Input, DataTable, Button
from textual.containers import VerticalScroll


class CompareView(VerticalScroll):
    DEFAULT_CSS = """
    CompareView {
        padding: 1 2;
    }
    CompareView Input {
        margin-bottom: 1;
    }
    CompareView DataTable {
        height: 1fr;
    }
    """

    _tickers: list[str] = []
    _rows: list[list[str]] = []

    def compose(self) -> ComposeResult:
        yield Static("Compare ETFs — Enter tickers separated by spaces")
        with Horizontal():
            yield Input(placeholder="e.g. VTI ITOT SCHB", id="compare-input")
            yield Button("Export", id="export-compare", variant="success")
        yield DataTable(id="compare-table")

    def on_mount(self) -> None:
        table = self.query_one("#compare-table", DataTable)
        table.add_column("Metric", key="metric")
        table.cursor_type = "row"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-compare":
            self._export()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "compare-input" and event.value.strip():
            tickers = event.value.strip().upper().split()[:5]
            self._tickers = tickers
            self.query_one("#compare-table", DataTable).loading = True
            self.run_worker(self._load(tickers), exclusive=True)

    async def _load(self, tickers: list[str]) -> None:
        from asyncio import to_thread
        from etf_terminal.data.edgar_service import get_holdings_df, get_etf_report
        from etf_terminal.domain.etf_analytics import calculate_concentration, calculate_weight_overlap

        table = self.query_one("#compare-table", DataTable)
        table.clear(columns=True)
        table.add_column("Metric", key="metric")
        for t in tickers:
            table.add_column(t, key=t)

        # Gather data
        reports = {}
        concentrations = {}
        holdings_dfs = {}
        for t in tickers:
            reports[t] = await to_thread(get_etf_report, t)
            df = await to_thread(get_holdings_df, t)
            holdings_dfs[t] = df
            if df is not None and not df.empty:
                concentrations[t] = calculate_concentration(df)

        self._rows = []

        def row(label: str, getter):
            r = [label] + [getter(t) for t in tickers]
            self._rows.append(r)
            return r

        table.add_row(*row("Fund Name", lambda t: (reports.get(t) and reports[t].fund_name[:20]) or "N/A"))
        table.add_row(*row("Holdings", lambda t: f"{reports[t].num_holdings:,}" if reports.get(t) else "N/A"))
        table.add_row(*row("Total Assets", lambda t: f"${float(reports[t].total_assets)/1e9:.1f}B" if reports.get(t) and reports[t].total_assets else "N/A"))
        table.add_row(*row("Top 10 Wt", lambda t: f"{concentrations[t].top10_weight:.1f}%" if t in concentrations else "N/A"))
        table.add_row(*row("Effective N", lambda t: f"{concentrations[t].effective_n:.0f}" if t in concentrations else "N/A"))
        table.add_row(*row("HHI", lambda t: f"{concentrations[t].hhi:.4f}" if t in concentrations else "N/A"))
        table.add_row(*row("Verdict", lambda t: concentrations[t].verdict if t in concentrations else "N/A"))
        table.add_row(*row("Period", lambda t: reports[t].reporting_period if reports.get(t) else "N/A"))

        # Weight-adjusted overlap vs first ticker
        if len(tickers) >= 2:
            first = tickers[0]
            first_df = holdings_dfs.get(first)

            def overlap_val(t):
                if t == first:
                    return "—"
                other_df = holdings_dfs.get(t)
                if first_df is None or other_df is None:
                    return "N/A"
                if first_df.empty or other_df.empty:
                    return "N/A"
                pct = calculate_weight_overlap(first_df, other_df)
                return f"{pct:.1f}%"

            table.add_row(*row(f"Wt Overlap vs {first}", overlap_val))

        # Zacks 52wk weighted average return
        from etf_terminal.data.zacks_service import get_holdings_from_zacks

        async def _avg_52wk(t: str) -> str:
            zdf = await to_thread(get_holdings_from_zacks, t)
            if zdf is None or zdf.empty or "week52_return" not in zdf.columns:
                return "N/A"
            total_w = zdf["pct_value"].sum()
            if total_w == 0:
                return "N/A"
            avg = (zdf["pct_value"] * zdf["week52_return"]).sum() / total_w
            return f"{avg:+.2f}%"

        avg_row = ["Avg 52wk Ret"] + [await _avg_52wk(t) for t in tickers]
        self._rows.append(avg_row)
        table.add_row(*avg_row)

        table.loading = False

    def _export(self) -> None:
        if not self._rows:
            self.app.notify("No data to export", severity="warning")
            return
        import pandas as pd
        from etf_terminal.data.export_service import export_dataframe_csv
        from etf_terminal.db.database import load_settings
        cols = ["Metric"] + self._tickers
        df = pd.DataFrame(self._rows, columns=cols)
        path = export_dataframe_csv(df, "compare_" + "_".join(self._tickers), load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
