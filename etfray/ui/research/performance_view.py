"""ETF Performance view — seasonals chart and period returns table."""

from __future__ import annotations

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Select, Static

_PLACEHOLDER_YEAR_OPTS: list[tuple[str, str]] = [("—", "")]


def _fmt_seasonal_pct(value: float) -> str:
    return f"{value:+.2f}%"


class PerformanceView(VerticalScroll):
    """Performance view — seasonals chart and period returns table."""

    DEFAULT_CSS = """
    PerformanceView {
        padding: 1 2;
    }
    PerformanceView #perf-header {
        height: auto;
        min-height: 3;
        width: 100%;
        margin-bottom: 1;
    }
    PerformanceView #perf-controls {
        height: auto;
        min-height: 3;
        width: 100%;
        margin-bottom: 1;
    }
    PerformanceView #perf-year-start,
    PerformanceView #perf-year-end {
        width: 14;
        min-width: 14;
        margin-right: 1;
    }
    PerformanceView #perf-header Button,
    PerformanceView #perf-controls Button {
        min-width: 8;
        max-width: 12;
        height: 3;
        margin: 0 0 0 1;
    }
    PerformanceView #perf-chart-row {
        width: 100%;
        height: auto;
        min-height: 16;
        margin-bottom: 1;
    }
    PerformanceView #perf-chart {
        width: 1fr;
        height: auto;
        min-height: 16;
    }
    PerformanceView #perf-legend {
        width: 20;
        min-width: 20;
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    PerformanceView #perf-table-scroll {
        height: auto;
        min-height: 10;
    }
    PerformanceView #perf-table-scroll.hidden {
        display: none;
    }
    PerformanceView #perf-table {
        height: auto;
        min-height: 10;
    }
    PerformanceView #perf-summary {
        height: auto;
        min-height: 2;
        color: $text-muted;
        margin-top: 1;
    }
    PerformanceView .hidden {
        display: none;
    }
    """

    _ticker: str = ""
    _display_mode: str = "chart"
    _show_average: bool = False
    _year_start: int = 0
    _year_end: int = 0
    _history_df: pd.DataFrame | None = None
    _prices: pd.Series | None = None
    _period_rows: list[tuple[str, float | None]] = []
    _available_years: list[int] = []
    _syncing_year_selects: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="perf-header"):
            yield Static("Performance — Select an ETF first", id="perf-title")
            yield Button("Chart", id="perf-chart-btn", variant="primary")
            yield Button("Table", id="perf-table-btn")
            yield Button("Export", id="perf-export", variant="success")
        with Horizontal(id="perf-controls"):
            yield Select(
                _PLACEHOLDER_YEAR_OPTS,
                prompt="Start year",
                id="perf-year-start",
                allow_blank=True,
            )
            yield Select(
                _PLACEHOLDER_YEAR_OPTS,
                prompt="End year",
                id="perf-year-end",
                allow_blank=True,
            )
            yield Button("Average", id="perf-average-btn")
        with Horizontal(id="perf-chart-row"):
            yield Static(
                "Select an ETF to view seasonals chart.",
                id="perf-chart",
                markup=False,
            )
            yield Static("", id="perf-legend", markup=False)
        with VerticalScroll(id="perf-table-scroll"):
            yield DataTable(id="perf-table")
        yield Static("", id="perf-summary")

    def on_mount(self) -> None:
        table = self.query_one("#perf-table", DataTable)
        table.add_column("Period", key="period")
        table.add_column("Return", key="return")
        table.cursor_type = "row"
        self._update_toggle_buttons()
        self._update_average_button()

    def on_resize(self) -> None:
        if self._prices is not None and self._display_mode == "chart":
            self._render_chart()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "perf-chart-btn":
            self._set_display_mode("chart")
        elif event.button.id == "perf-table-btn":
            self._set_display_mode("table")
        elif event.button.id == "perf-export":
            self._export()
        elif event.button.id == "perf-average-btn":
            self._show_average = not self._show_average
            self._update_average_button()
            if self._prices is not None:
                self._render_chart()

    def on_select_changed(self, event: Select.Changed) -> None:
        if self._syncing_year_selects:
            return
        if event.select.id not in ("perf-year-start", "perf-year-end"):
            return
        if not event.value or event.value == "":
            return
        try:
            year = int(event.value)
        except (TypeError, ValueError):
            return

        if event.select.id == "perf-year-start":
            self._year_start = year
        else:
            self._year_end = year

        if self._year_start and self._year_end and self._year_start > self._year_end:
            self._year_start, self._year_end = self._year_end, self._year_start
            self._sync_year_selects()

        if self._prices is not None and self._year_start and self._year_end:
            self._render_chart()

    def _sync_year_selects(self) -> None:
        """Keep both Select widgets aligned after range normalization."""
        self._syncing_year_selects = True
        try:
            self.query_one("#perf-year-start", Select).value = str(self._year_start)
            self.query_one("#perf-year-end", Select).value = str(self._year_end)
        finally:
            self._syncing_year_selects = False

    def load_etf(self, ticker: str) -> None:
        self._ticker = ticker.upper()
        self.query_one("#perf-title", Static).update(f"{self._ticker} — Performance (Seasonals)")
        self._set_loading(True)
        self.run_worker(self._load(self._ticker), exclusive=True)

    def _set_loading(self, loading: bool) -> None:
        self.query_one("#perf-chart", Static).loading = loading
        self.query_one("#perf-table", DataTable).loading = loading

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread

        from etfray.data.price_history_service import get_price_history, get_price_history_last_error
        from etfray.domain.overview_format import fmt_pct
        from etfray.domain.performance_analytics import (
            _adj_close_series,
            available_years,
            compute_period_returns,
            compute_summary,
        )

        df = await to_thread(get_price_history, ticker, "max")
        chart = self.query_one("#perf-chart", Static)
        table = self.query_one("#perf-table", DataTable)
        summary = self.query_one("#perf-summary", Static)

        chart.loading = False
        table.loading = False

        if df is None or df.empty:
            err = get_price_history_last_error() or "No price history available"
            chart.update(f"Error: {err}")
            self.query_one("#perf-legend", Static).update("")
            table.clear()
            summary.update(f"Error: {err}")
            self._history_df = None
            self._prices = None
            self._period_rows = []
            self._available_years = []
            self._reset_year_selects()
            return

        self._history_df = df
        self._prices = _adj_close_series(df)
        self._period_rows = compute_period_returns(df)
        self._available_years = available_years(self._prices)
        self._populate_year_selects()
        perf_summary = compute_summary(df)

        table.clear()
        for label, ret in self._period_rows:
            table.add_row(label, fmt_pct(ret, signed=True))

        self.set_timer(0.05, self._render_chart)
        total_str = fmt_pct(perf_summary.total_return, signed=True)
        year_range = f"{self._year_start}–{self._year_end}" if self._available_years else "N/A"
        summary.update(
            f"{self._ticker} | {year_range} | Total return {total_str} | "
            f"{perf_summary.start_date} → {perf_summary.end_date} | Source: Yahoo Finance"
        )

    def _reset_year_selects(self) -> None:
        self._year_start = 0
        self._year_end = 0
        start_select = self.query_one("#perf-year-start", Select)
        end_select = self.query_one("#perf-year-end", Select)
        start_select.set_options(_PLACEHOLDER_YEAR_OPTS)
        end_select.set_options(_PLACEHOLDER_YEAR_OPTS)

    def _populate_year_selects(self) -> None:
        years = self._available_years
        if not years:
            self._reset_year_selects()
            return

        options = [(str(y), str(y)) for y in years]
        start_select = self.query_one("#perf-year-start", Select)
        end_select = self.query_one("#perf-year-end", Select)

        if len(years) > 6:
            self._year_start = years[-6]
        else:
            self._year_start = years[0]
        self._year_end = years[-1]

        start_select.set_options(options)
        end_select.set_options(options)
        self._sync_year_selects()

    def _chart_dimensions(self) -> tuple[int, int]:
        """Fit plotext canvas to available terminal width (legend uses ~22 cols)."""
        view_width = self.size.width or 0
        if view_width < 40:
            try:
                view_width = self.app.size.width
            except Exception:
                view_width = 100
        width = max(50, min(view_width - 28, 100))
        return width, 18

    def _render_chart(self) -> None:
        if self._prices is None or not self._year_start or not self._year_end:
            return

        from etfray.domain.performance_analytics import compute_seasonals
        from etfray.domain.seasonals_plot import render_seasonals_chart

        series_list, average = compute_seasonals(
            self._prices,
            self._year_start,
            self._year_end,
            include_average=self._show_average,
        )
        if not series_list:
            self.query_one("#perf-chart", Static).update("No seasonal data for selected years.")
            self.query_one("#perf-legend", Static).update("")
            return

        width, height = self._chart_dimensions()
        chart_text = render_seasonals_chart(series_list, average, width=width, height=height)
        self.query_one("#perf-chart", Static).update(chart_text or "Chart unavailable.")

        legend_lines = []
        for series in sorted(series_list, key=lambda s: s.year, reverse=True):
            legend_lines.append(f"{series.year}: {_fmt_seasonal_pct(series.final_return_pct)}")
        if average is not None and average.day_of_year:
            legend_lines.append(f"Avg: {_fmt_seasonal_pct(average.final_return_pct)}")
        self.query_one("#perf-legend", Static).update("\n".join(legend_lines) if legend_lines else "")

    def _set_display_mode(self, mode: str) -> None:
        self._display_mode = mode
        chart_row = self.query_one("#perf-chart-row")
        table_scroll = self.query_one("#perf-table-scroll")
        if mode == "chart":
            chart_row.remove_class("hidden")
            table_scroll.add_class("hidden")
            if self._prices is not None:
                self._render_chart()
        else:
            chart_row.add_class("hidden")
            table_scroll.remove_class("hidden")
        self._update_toggle_buttons()

    def _update_toggle_buttons(self) -> None:
        chart_btn = self.query_one("#perf-chart-btn", Button)
        table_btn = self.query_one("#perf-table-btn", Button)
        if self._display_mode == "chart":
            chart_btn.variant = "primary"
            table_btn.variant = "default"
        else:
            chart_btn.variant = "default"
            table_btn.variant = "primary"

    def _update_average_button(self) -> None:
        btn = self.query_one("#perf-average-btn", Button)
        btn.variant = "primary" if self._show_average else "default"

    def _export(self) -> None:
        if self._history_df is None or self._prices is None:
            self.app.notify("No data to export", severity="warning")
            return

        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings
        from etfray.domain.performance_analytics import compute_seasonals, seasonals_to_export_rows

        series_list, _ = compute_seasonals(
            self._prices,
            self._year_start,
            self._year_end,
            include_average=False,
        )
        export_df = seasonals_to_export_rows(series_list, self._prices)
        if export_df.empty:
            self.app.notify("No seasonal data to export", severity="warning")
            return

        path = export_dataframe_csv(
            export_df,
            f"{self._ticker}_seasonals_{self._year_start}_{self._year_end}",
            load_settings().export_dir,
        )
        self.app.notify(f"Exported to {path}")
