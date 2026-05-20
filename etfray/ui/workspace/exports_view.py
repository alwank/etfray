"""Exports view - export research and analytics data."""

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Select, Static

from etfray.db.database import load_settings

EXPORT_TARGETS = [
    ("ETF Holdings", "holdings"),
    ("ETF Exposure", "exposure"),
    ("Portfolio Positions", "positions"),
    ("ETF Lookthrough", "lookthrough"),
    ("Margin Summary", "margin"),
]

EXPORT_FORMATS = [
    ("CSV", "csv"),
    ("JSON", "json"),
    ("Markdown", "md"),
]


class ExportsView(VerticalScroll):
    DEFAULT_CSS = """
    ExportsView {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]Export Data[/bold]")
        with Horizontal():
            yield Select(
                [(label, val) for label, val in EXPORT_TARGETS],
                prompt="Select data to export",
                id="export-target",
            )
            yield Select(
                [(label, val) for label, val in EXPORT_FORMATS],
                prompt="Format",
                id="export-format",
            )
            yield Button("Export", id="btn-export", variant="primary")
        yield Static("Select a target and format, then click Export.", id="export-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-export":
            self.run_worker(self._export(), exclusive=True)

    async def _export(self) -> None:
        target_sel = self.query_one("#export-target", Select)
        format_sel = self.query_one("#export-format", Select)
        status = self.query_one("#export-status", Static)

        target = target_sel.value
        fmt = format_sel.value

        if target is Select.BLANK or fmt is Select.BLANK:
            status.update("Please select both target and format.")
            return

        settings = load_settings()
        export_dir = Path(settings.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        ticker = getattr(self.app, "_current_etf", None) or "portfolio"
        filename = f"{ticker}_{target}.{fmt}"
        filepath = export_dir / filename

        data = self._get_data(str(target), ticker)
        if not data:
            status.update(f"No data available for {target}.")
            return

        if fmt == "csv":
            self._write_csv(filepath, data)
        elif fmt == "json":
            filepath.write_text(json.dumps(data, indent=2, default=str))
        elif fmt == "md":
            self._write_md(filepath, data, str(target))

        status.update(f"Exported to: {filepath}")

    def _get_data(self, target: str, ticker: str) -> list[dict] | None:
        if target == "holdings":
            from etfray.data.edgar_service import get_holdings_df
            df = get_holdings_df(ticker)
            if df is not None and not df.empty:
                return df.head(100).to_dict("records")
        elif target == "positions":
            from etfray.data.ibkr_service import get_ibkr_service
            svc = get_ibkr_service()
            if svc.positions:
                return [{"symbol": p.symbol, "qty": p.quantity, "avg_cost": p.avg_cost, "value": p.market_value} for p in svc.positions]
        elif target == "margin":
            from etfray.data.ibkr_service import get_ibkr_service
            svc = get_ibkr_service()
            if svc.account_summary:
                s = svc.account_summary
                return [s.__dict__]
        return None

    def _write_csv(self, path: Path, data: list[dict]) -> None:
        if not data:
            return
        import csv
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

    def _write_md(self, path: Path, data: list[dict], title: str) -> None:
        if not data:
            return
        lines = [f"# {title}\n"]
        headers = list(data[0].keys())
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in data[:50]:
            lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
        path.write_text("\n".join(lines))
