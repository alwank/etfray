"""ETF Compare view - side-by-side comparison of 2-5 ETFs."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static


class CompareView(Vertical):
    DEFAULT_CSS = """
    CompareView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 2;
        layout: grid;
        grid-size: 1 2;
        grid-rows: auto 1fr;
        grid-gutter: 0 1;
    }
    CompareView #compare-toolbar {
        height: auto;
        width: 100%;
        row-span: 1;
        layout: vertical;
    }
    CompareView #compare-toolbar Horizontal {
        height: auto;
        min-height: 3;
        width: 100%;
    }
    CompareView #compare-input {
        height: 3;
        min-height: 3;
        width: 1fr;
        margin-bottom: 1;
    }
    CompareView #export-compare {
        height: 3;
        min-height: 3;
        margin-left: 1;
    }
    CompareView #compare-table {
        width: 100%;
        height: 100%;
        min-height: 0;
        row-span: 1;
    }
    """

    _tickers: list[str] = []
    _rows: list[list[str]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="compare-toolbar"):
            yield Static("Compare ETFs — Enter tickers separated by spaces")
            with Horizontal():
                yield Input(placeholder="e.g. VTI ITOT SCHB", id="compare-input")
                yield Button("Export", id="export-compare")
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
            self.loading = True
            self.run_worker(self._load(tickers), exclusive=True)

    async def _load(self, tickers: list[str]) -> None:
        from asyncio import to_thread

        from etfray.data.edgar_service import get_etf_report, get_holdings_df
        from etfray.data.market_data_service import get_etf_profile
        from etfray.domain.etf_analytics import calculate_concentration, calculate_weight_overlap
        from etfray.domain.overview_format import fmt_expense_ratio, fmt_pct

        table = self.query_one("#compare-table", DataTable)
        table.clear(columns=True)
        table.add_column("Metric", key="metric")
        for t in tickers:
            table.add_column(t, key=t)

        # Gather data
        reports = {}
        profiles = {}
        concentrations = {}
        holdings_dfs = {}
        for t in tickers:
            reports[t] = await to_thread(get_etf_report, t)
            profiles[t], _ = await to_thread(get_etf_profile, t)
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
        table.add_row(*row("Category", lambda t: (profiles.get(t) and profiles[t].category) or "N/A"))
        table.add_row(
            *row("Expense Ratio", lambda t: fmt_expense_ratio(profiles[t].expense_ratio) if profiles.get(t) else "N/A")
        )
        table.add_row(*row("Div Yield", lambda t: fmt_pct(profiles[t].dividend_yield) if profiles.get(t) else "N/A"))
        table.add_row(
            *row(
                "YTD Return",
                lambda t: (
                    fmt_pct(profiles[t].ytd_return, signed=True)
                    if profiles.get(t) and profiles[t].ytd_return is not None
                    else "N/A"
                ),
            )
        )
        table.add_row(
            *row(
                "Beta (3Y)",
                lambda t: f"{profiles[t].beta:.2f}" if profiles.get(t) and profiles[t].beta is not None else "N/A",
            )
        )
        table.add_row(*row("Holdings", lambda t: f"{reports[t].num_holdings:,}" if reports.get(t) else "N/A"))
        table.add_row(
            *row(
                "Total Assets",
                lambda t: (
                    f"${float(reports[t].total_assets) / 1e9:.1f}B"
                    if reports.get(t) and reports[t].total_assets
                    else "N/A"
                ),
            )
        )
        table.add_row(
            *row("Top 10 Wt", lambda t: f"{concentrations[t].top10_weight:.1f}%" if t in concentrations else "N/A")
        )
        table.add_row(
            *row("Effective N", lambda t: f"{concentrations[t].effective_n:.0f}" if t in concentrations else "N/A")
        )
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

        # Web 52wk weighted average return
        from etfray.data.web_service import get_holdings_from_web

        async def _avg_52wk(t: str) -> str:
            zdf = await to_thread(get_holdings_from_web, t)
            if zdf is None or zdf.empty or "week52_return" not in zdf.columns:
                return "N/A"
            total_w = zdf["pct_value"].sum()
            if total_w == 0:
                return "N/A"
            avg = (zdf["pct_value"] * zdf["week52_return"]).sum() / total_w
            return fmt_pct(avg, signed=True)

        avg_row = ["Avg 52wk Ret"] + [await _avg_52wk(t) for t in tickers]
        self._rows.append(avg_row)
        table.add_row(*avg_row)

        self.loading = False

    def _export(self) -> None:
        if not self._rows:
            self.app.notify("No data to export", severity="warning")
            return
        import pandas as pd

        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings

        cols = ["Metric"] + self._tickers
        df = pd.DataFrame(self._rows, columns=cols)
        path = export_dataframe_csv(df, "compare_" + "_".join(self._tickers), load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
