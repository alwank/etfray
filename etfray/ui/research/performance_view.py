"""ETF Performance view — seasonals chart and period returns table."""

from __future__ import annotations

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.timer import Timer
from textual.widgets import Button, DataTable, Select, Static

from etfray.domain.seasonals_plot import (
    DEFAULT_CHART_ROWS,
    chart_deps_status,
    chart_image_status,
    chart_pixel_dimensions,
    charts_available,
    color_for_series_index,
    render_seasonals_chart,
    render_seasonals_figure,
    terminal_cell_size,
)

try:
    from textual_image.widget import Image as TerminalImage

    _TERMINAL_IMAGE_CLASS = TerminalImage
except ImportError:
    _TERMINAL_IMAGE_CLASS = None

_PLACEHOLDER_YEAR_OPTS: list[tuple[str, str]] = [("—", "")]
_CHART_IMAGE_DPI = 150


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
        min-height: 24;
        margin-bottom: 1;
    }
    PerformanceView #perf-chart-container {
        width: 1fr;
        height: auto;
        min-height: 24;
    }
    PerformanceView #perf-chart-image {
        height: auto;
        min-height: 20;
        width: auto;
        max-width: 100%;
        border: solid $primary-background;
    }
    PerformanceView #perf-chart-fallback {
        width: 100%;
        height: auto;
        min-height: 16;
    }
    PerformanceView #perf-chart-status {
        width: 100%;
        height: 1;
        color: $text-muted;
        display: none;
    }
    PerformanceView #perf-chart-status.visible {
        display: block;
    }
    PerformanceView #perf-legend {
        width: 22;
        min-width: 18;
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
    _chart_mode: str = "none"
    _resize_timer: Timer | None = None
    _summary_base: str = ""
    _has_chart_image_widget: bool = False
    _last_render_cells: tuple[int, int] = (0, 0)
    _needs_layout_rerender: bool = False
    _chart_render_cache: tuple[list, object | None, str] | None = None

    def _chart_image_widget(self):
        """Return the image chart widget if it was composed, else None."""
        if not self._has_chart_image_widget:
            return None
        return self.query_one("#perf-chart-image")

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
            yield Static("", id="perf-chart-status")
            with Horizontal(id="perf-chart-container"):
                self._has_chart_image_widget = _TERMINAL_IMAGE_CLASS is not None
                if _TERMINAL_IMAGE_CLASS is not None:
                    yield _TERMINAL_IMAGE_CLASS(id="perf-chart-image")
                yield Static(
                    "Select an ETF to view seasonals chart.",
                    id="perf-chart-fallback",
                    markup=False,
                )
            yield Static("", id="perf-legend")
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
        if charts_available() and not self._has_chart_image_widget:
            self.app.notify(
                "textual-image widget unavailable — reinstall etfray[charts]",
                severity="warning",
            )
        if charts_available() and self._has_chart_image_widget:
            self._set_chart_mode("image")
        else:
            self._set_chart_mode("fallback")
        self._update_summary_chart_status()

    def on_resize(self) -> None:
        if self._prices is None or self._display_mode != "chart":
            return
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(0.15, self._render_chart)

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
        status = self.query_one("#perf-chart-status", Static)
        fallback = self.query_one("#perf-chart-fallback", Static)
        if loading:
            status.update("Loading chart…")
            status.add_class("visible")
            fallback.loading = True
            image = self._chart_image_widget()
            if image is not None:
                image.add_class("hidden")
        else:
            status.remove_class("visible")
            status.update("")
            fallback.loading = False
        self.query_one("#perf-table", DataTable).loading = loading

    def _set_chart_mode(self, mode: str) -> None:
        """Show image widget or plotext fallback static."""
        self._chart_mode = mode
        image = self._chart_image_widget()
        fallback = self.query_one("#perf-chart-fallback", Static)
        if mode == "image" and image is not None:
            image.remove_class("hidden")
            fallback.add_class("hidden")
        else:
            if image is not None:
                image.add_class("hidden")
            fallback.remove_class("hidden")

    def _chart_cell_size(self) -> tuple[int, int]:
        """Chart area size in terminal cells (cols, rows)."""
        widget = self._chart_image_widget()
        if widget is not None and widget.size.width > 0 and widget.size.height > 0:
            return widget.size.width, widget.size.height

        view_w = self.size.width or 0
        if view_w < 40:
            try:
                view_w = self.app.size.width
            except Exception:
                view_w = 80
        cols = max(40, view_w - 28)
        return cols, DEFAULT_CHART_ROWS

    def _chart_pixel_size(self) -> tuple[int, int, int, int]:
        """Return (cols, rows, width_px, height_px) with supersampling."""
        cols, rows = self._chart_cell_size()
        return chart_pixel_dimensions(cols, rows, cell_size=terminal_cell_size())

    def _apply_chart_widget_size(self, cols: int, rows: int) -> None:
        """Pin image widget to 1:1 cell mapping to avoid upscaling a small PNG."""
        widget = self._chart_image_widget()
        if widget is None:
            return
        widget.styles.width = cols
        widget.styles.height = rows

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

    def _update_summary_chart_status(self) -> None:
        """Append chart backend status to the summary line."""
        if not self._summary_base:
            return
        summary = self.query_one("#perf-summary", Static)
        if self._chart_mode == "image":
            status = chart_image_status()
        elif self._chart_mode == "fallback":
            status = chart_deps_status()
        else:
            status = chart_deps_status()
        summary.update(f"{self._summary_base} | {status}")

    def _show_chart_error(self, message: str) -> None:
        self.query_one("#perf-legend", Static).update("")
        self._set_chart_mode("fallback")
        self.query_one("#perf-chart-fallback", Static).update(message)

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
        table = self.query_one("#perf-table", DataTable)
        summary = self.query_one("#perf-summary", Static)

        self._set_loading(False)

        if df is None or df.empty:
            err = get_price_history_last_error() or "No price history available"
            self._show_chart_error(f"Error: {err}")
            table.clear()
            summary.update(f"Error: {err}")
            self._history_df = None
            self._prices = None
            self._period_rows = []
            self._available_years = []
            self._summary_base = ""
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
        self._summary_base = (
            f"{self._ticker} | {year_range} | Total return {total_str} | "
            f"{perf_summary.start_date} → {perf_summary.end_date} | Source: Yahoo Finance"
        )
        self._update_summary_chart_status()

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

    def _update_legend(self, series_list: list, average) -> None:
        sorted_asc = sorted(series_list, key=lambda s: s.year)
        lines = []
        for s in sorted(series_list, key=lambda s: s.year, reverse=True):
            idx = next(i for i, x in enumerate(sorted_asc) if x.year == s.year)
            hex_color = color_for_series_index(idx)
            lines.append(f"[{hex_color}]■[/] {s.year}  {_fmt_seasonal_pct(s.final_return_pct)}")
        if average is not None and average.day_of_year:
            lines.append(f"[bold white]--[/] Avg  {_fmt_seasonal_pct(average.final_return_pct)}")
        self.query_one("#perf-legend", Static).update("\n".join(lines) if lines else "")

    def _render_chart_fallback(self, series_list, average) -> None:
        width, height = self._chart_dimensions()
        chart_text = render_seasonals_chart(series_list, average, width=width, height=height)
        self.query_one("#perf-chart-fallback", Static).update(chart_text or "Chart unavailable.")
        self._set_chart_mode("fallback")
        self._update_summary_chart_status()

    def _finish_layout_rerender(self) -> None:
        """Re-render once the image widget has real layout dimensions."""
        if not self._needs_layout_rerender or self._chart_render_cache is None:
            return
        widget = self._chart_image_widget()
        if widget is None or widget.size.width == 0 or widget.size.height == 0:
            return
        cols, rows = self._chart_cell_size()
        if (cols, rows) == self._last_render_cells:
            self._needs_layout_rerender = False
            return
        self._needs_layout_rerender = False
        series_list, average, title = self._chart_render_cache
        self.run_worker(
            self._render_chart_image(series_list, average, title),
            exclusive=True,
            group="perf-chart",
        )

    async def _render_chart_image(self, series_list, average, title: str) -> None:
        from asyncio import to_thread
        from io import BytesIO

        from PIL import Image as PILImage

        widget = self._chart_image_widget()
        used_estimate = widget is None or widget.size.width == 0 or widget.size.height == 0
        cols, rows, width_px, height_px = self._chart_pixel_size()
        try:
            png = await to_thread(
                render_seasonals_figure,
                series_list,
                average,
                title=title,
                width_px=width_px,
                height_px=height_px,
                dpi=_CHART_IMAGE_DPI,
            )
        except Exception as exc:
            self.app.notify(f"Chart render failed: {exc}", severity="warning")
            self._render_chart_fallback(series_list, average)
            return

        if widget is None:
            self._render_chart_fallback(series_list, average)
            return
        widget.image = PILImage.open(BytesIO(png))
        self._apply_chart_widget_size(cols, rows)
        self._last_render_cells = (cols, rows)
        self._set_chart_mode("image")
        self._update_summary_chart_status()
        if used_estimate:
            self._needs_layout_rerender = True
            self.call_after_refresh(self._finish_layout_rerender)

    def _render_chart(self) -> None:
        if self._prices is None or not self._year_start or not self._year_end:
            return

        from etfray.domain.performance_analytics import compute_seasonals

        series_list, average = compute_seasonals(
            self._prices,
            self._year_start,
            self._year_end,
            include_average=self._show_average,
        )
        if not series_list:
            self._show_chart_error("No seasonal data for selected years.")
            return

        title = f"{self._ticker} Seasonals ({self._year_start}–{self._year_end})"
        self._update_legend(series_list, average)
        self._chart_render_cache = (series_list, average, title)

        use_image = charts_available() and self._has_chart_image_widget
        if charts_available() and not self._has_chart_image_widget:
            self.app.notify(
                "textual-image widget unavailable — reinstall etfray[charts]",
                severity="warning",
            )
        if use_image:
            self.run_worker(
                self._render_chart_image(series_list, average, title),
                exclusive=True,
                group="perf-chart",
            )
        else:
            self._render_chart_fallback(series_list, average)

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
