"""ETF Concentration view - top N weights, HHI, effective holdings, group concentration."""

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static


class ConcentrationView(VerticalScroll):
    DEFAULT_CSS = """
    ConcentrationView {
        padding: 1 2;
    }
    ConcentrationView Horizontal {
        height: auto;
    }
    ConcentrationView #conc-content {
        height: auto;
    }
    """

    _ticker: str = ""
    _lines: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Concentration — Select an ETF first", id="conc-title")
            yield Button("Export", id="export-conc", variant="success")
        yield Static("", id="conc-content")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-conc":
            self._export()

    def load_etf(self, ticker: str) -> None:
        self._ticker = ticker
        content = self.query_one("#conc-content", Static)
        content.update("")
        content.loading = True
        self.run_worker(self._load(ticker), exclusive=True)

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread

        from etfray.data.source_resolver import resolve_holdings
        from etfray.domain.etf_analytics import (
            ASSET_CATEGORY_MAP,
            calculate_concentration,
            calculate_group_concentration,
        )

        title = self.query_one("#conc-title", Static)
        content = self.query_one("#conc-content", Static)

        preference = getattr(self.app, "_data_source", "auto")
        df, source = await to_thread(resolve_holdings, ticker, preference)

        if df is None or df.empty:
            content.loading = False
            content.update("Holdings unavailable")
            title.update(f"Concentration — {ticker}")
            return

        m = calculate_concentration(df)
        title.update(f"Concentration — {ticker} │ {source.upper()}")

        lines = [
            "[bold]Holdings Concentration[/bold]",
            f"  Holdings:          {m.num_holdings:,}",
            f"  Largest:           {m.largest_holding} ({m.top1_weight:.2f}%)",
            f"  Top 5:             {m.top5_weight:.1f}%",
            f"  Top 10:            {m.top10_weight:.1f}%",
            f"  Top 25:            {m.top25_weight:.1f}%",
            f"  Effective N:       {m.effective_n:.0f}",
            f"  HHI:               {m.hhi:.6f}",
            f"  Verdict:           {m.verdict}",
        ]

        # Country concentration
        gc = calculate_group_concentration(df, "investment_country")
        if gc:
            lines += [
                "",
                f"[bold]Country Concentration[/bold]  ({gc.num_groups} countries)",
            ]
            for name, wt in gc.entries:
                lines.append(f"  {name:<20} {wt:.1f}%")
            lines.append(f"  Top 1:  {gc.top1_weight:.1f}%  │  Top 3:  {gc.top3_weight:.1f}%  │  HHI: {gc.hhi:.4f}")

        # Asset type concentration
        ga = calculate_group_concentration(df, "asset_category")
        if ga:
            lines += [
                "",
                f"[bold]Asset Type Concentration[/bold]  ({ga.num_groups} types)",
            ]
            for name, wt in ga.entries:
                label = ASSET_CATEGORY_MAP.get(name, name) if name else "Unclassified"
                lines.append(f"  {label:<25} {wt:.1f}%")
            lines.append(f"  Top 1:  {ga.top1_weight:.1f}%  │  HHI: {ga.hhi:.4f}")

        self._lines = lines
        content.loading = False
        content.update("\n".join(lines))

    def _export(self) -> None:
        if not self._lines:
            self.app.notify("No data to export", severity="warning")
            return
        import pandas as pd

        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings
        # Export as plain text rows
        df = pd.DataFrame({"line": [line.strip() for line in self._lines if line.strip()]})
        path = export_dataframe_csv(df, f"{self._ticker}_concentration", load_settings().export_dir)
        self.app.notify(f"Exported to {path}")
