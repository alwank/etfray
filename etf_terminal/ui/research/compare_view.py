"""ETF Compare view - side-by-side comparison of 2-5 ETFs."""

from textual.app import ComposeResult
from textual.widgets import Static, Input, DataTable
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

    def compose(self) -> ComposeResult:
        yield Static("Compare ETFs — Enter tickers separated by spaces")
        yield Input(placeholder="e.g. VTI ITOT SCHB", id="compare-input")
        yield DataTable(id="compare-table")

    def on_mount(self) -> None:
        table = self.query_one("#compare-table", DataTable)
        table.add_column("Metric", key="metric")
        table.cursor_type = "row"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "compare-input" and event.value.strip():
            tickers = event.value.strip().upper().split()[:5]
            self.run_worker(self._load(tickers), exclusive=True)

    async def _load(self, tickers: list[str]) -> None:
        from etf_terminal.data.edgar_service import get_holdings_df, get_etf_report
        from etf_terminal.domain.etf_analytics import calculate_concentration

        table = self.query_one("#compare-table", DataTable)
        table.clear(columns=True)
        table.add_column("Metric", key="metric")

        for t in tickers:
            table.add_column(t, key=t)

        # Gather data
        reports = {}
        concentrations = {}
        for t in tickers:
            reports[t] = get_etf_report(t)
            df = get_holdings_df(t)
            if df is not None and not df.empty:
                concentrations[t] = calculate_concentration(df)

        # Build comparison rows
        def row(label: str, getter):
            return [label] + [getter(t) for t in tickers]

        table.add_row(*row("Fund Name", lambda t: (reports.get(t) and reports[t].fund_name[:20]) or "N/A"))
        table.add_row(*row("Holdings", lambda t: f"{reports[t].num_holdings:,}" if reports.get(t) else "N/A"))
        table.add_row(*row("Total Assets", lambda t: f"${float(reports[t].total_assets)/1e9:.1f}B" if reports.get(t) and reports[t].total_assets else "N/A"))
        table.add_row(*row("Top 10 Wt", lambda t: f"{concentrations[t].top10_weight:.1f}%" if t in concentrations else "N/A"))
        table.add_row(*row("Effective N", lambda t: f"{concentrations[t].effective_n:.0f}" if t in concentrations else "N/A"))
        table.add_row(*row("HHI", lambda t: f"{concentrations[t].hhi:.4f}" if t in concentrations else "N/A"))
        table.add_row(*row("Verdict", lambda t: concentrations[t].verdict if t in concentrations else "N/A"))
        table.add_row(*row("Period", lambda t: reports[t].reporting_period if reports.get(t) else "N/A"))

        # Overlap calculation
        if len(tickers) >= 2:
            holdings_sets = {}
            for t in tickers:
                df = get_holdings_df(t)
                if df is not None and "ticker" in df.columns:
                    holdings_sets[t] = set(df["ticker"].dropna().astype(str).str.upper())

            if len(holdings_sets) >= 2:
                first = tickers[0]
                overlaps = []
                for t in tickers:
                    if t == first:
                        overlaps.append("—")
                    elif t in holdings_sets and first in holdings_sets:
                        shared = len(holdings_sets[first] & holdings_sets[t])
                        union = len(holdings_sets[first] | holdings_sets[t])
                        pct = (shared / union * 100) if union else 0
                        overlaps.append(f"{pct:.0f}%")
                    else:
                        overlaps.append("N/A")
                table.add_row(*([f"Overlap vs {first}"] + overlaps))

        # Zacks 52wk weighted average return
        from etf_terminal.data.zacks_service import get_holdings_from_zacks

        def _avg_52wk(t: str) -> str:
            zdf = get_holdings_from_zacks(t)
            if zdf is None or zdf.empty or "week52_return" not in zdf.columns:
                return "N/A"
            total_w = zdf["pct_value"].sum()
            if total_w == 0:
                return "N/A"
            avg = (zdf["pct_value"] * zdf["week52_return"]).sum() / total_w
            return f"{avg:+.2f}%"

        table.add_row(*row("Avg 52wk Ret", _avg_52wk))
