"""ETF Seasonals view — seasonals chart and period returns table."""

from __future__ import annotations

import pandas as pd
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, DataTable, Select, Static, TabbedContent, TabPane

from etfray.domain.seasonals_plot import (
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
_MIN_CHART_ROWS = 12
_LEGEND_SEPARATOR = "    ·    "


def _fmt_seasonal_pct(value: float) -> str:
    return f"{value:+.2f}%"


class SeasonalsView(Vertical):
    """Seasonals view — seasonals chart and period returns table."""

    # Sixel/ANSI chart output can leak into Textual as keypresses; consume app nav keys.
    BINDINGS = [
        Binding("escape", "consume_graphics_key", show=False, priority=True),
        Binding("c", "consume_graphics_key", show=False, priority=True),
        Binding("h", "consume_graphics_key", show=False, priority=True),
        Binding("t", "consume_graphics_key", show=False, priority=True),
        Binding("x", "consume_graphics_key", show=False, priority=True),
        Binding("r", "consume_graphics_key", show=False, priority=True),
        Binding("d", "consume_graphics_key", show=False, priority=True),
        Binding("m", "consume_graphics_key", show=False, priority=True),
        Binding("p", "consume_graphics_key", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    SeasonalsView {
        height: 1fr;
        min-height: 1fr;
        padding: 1 1;
    }
    SeasonalsView #perf-empty Button {
        margin-top: 1;
    }
    SeasonalsView #perf-body {
        display: none;
        height: 1fr;
        layout: grid;
        grid-size: 1 3;
        grid-gutter: 0 1;
        grid-rows: auto auto 1fr;
    }
    SeasonalsView #perf-header {
        height: auto;
        min-height: 1;
        width: 100%;
    }
    SeasonalsView #perf-controls {
        height: auto;
        min-height: 5;
        width: 100%;
        margin-bottom: 1;
    }
    SeasonalsView #perf-year-start,
    SeasonalsView #perf-year-end {
        width: 18;
        min-width: 18;
        margin-right: 1;
    }
    SeasonalsView #perf-header Button,
    SeasonalsView #perf-controls Button {
        min-width: 8;
        max-width: 12;
        margin: 0 0 0 1;
    }
    SeasonalsView TabbedContent {
        height: 1fr;
        width: 100%;
    }
    SeasonalsView TabbedContent > Vertical {
        height: 1fr;
    }
    SeasonalsView TabbedContent ContentSwitcher {
        height: 1fr;
        min-height: 0;
    }
    SeasonalsView TabPane {
        height: 1fr;
        min-height: 0;
        padding: 0;
    }
    SeasonalsView #tab-chart {
        layout: grid;
        grid-size: 1 2;
        grid-rows: 1fr auto;
        height: 1fr;
    }
    SeasonalsView #perf-chart-area {
        height: 1fr;
        min-height: 0;
        width: 100%;
    }
    SeasonalsView #perf-footer {
        height: auto;
        min-height: 8;
        width: 100%;
        background: $background;
    }
    SeasonalsView #perf-chart-container {
        height: 1fr;
        width: 100%;
        min-height: 12;
        overflow: hidden;
    }
    SeasonalsView #perf-chart-image {
        height: auto;
        width: auto;
        max-width: 100%;
        border: none;
    }
    SeasonalsView #perf-chart-fallback {
        width: 100%;
        height: auto;
        max-height: 100%;
    }
    SeasonalsView #perf-legend {
        width: 100%;
        height: auto;
        min-height: 1;
        padding: 1 0;
        color: $text-muted;
    }
    SeasonalsView #perf-table {
        height: 3;
        min-height: 3;
        width: 100%;
        margin-bottom: 1;
        overflow-x: hidden;
        overflow-y: hidden;
    }
    SeasonalsView #perf-summary {
        height: auto;
        min-height: 2;
        color: $text-muted;
    }
    SeasonalsView #tab-table {
        height: 1fr;
    }
    SeasonalsView #perf-monthly-table {
        height: 1fr;
        width: 100%;
    }
    SeasonalsView .hidden {
        display: none;
    }
    """

    _ticker: str = ""
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
    _monthly_table = None

    def _chart_image_widget(self):
        """Return the image chart widget if it was composed, else None."""
        if not self._has_chart_image_widget:
            return None
        return self.query_one("#perf-chart-image")

    def action_consume_graphics_key(self) -> None:
        """Block app-level nav shortcuts while this view is focused."""

    def compose(self) -> ComposeResult:
        with Vertical(id="perf-empty"):
            yield Static("Seasonals — Select an ETF first")
            yield Button("Open Search to select an ETF →", id="perf-open-search", variant="primary")
        with Vertical(id="perf-body"):
            with Horizontal(id="perf-header"):
                yield Static("", id="perf-title")
                yield Button("Export", id="perf-export")
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
            with TabbedContent(id="perf-tabs"):
                with TabPane("Chart", id="tab-chart"):
                    with Vertical(id="perf-chart-area"):
                        with Horizontal(id="perf-chart-container"):
                            self._has_chart_image_widget = _TERMINAL_IMAGE_CLASS is not None
                            if _TERMINAL_IMAGE_CLASS is not None:
                                yield _TERMINAL_IMAGE_CLASS(id="perf-chart-image")
                            yield Static(
                                "Select an ETF to view seasonals chart.",
                                id="perf-chart-fallback",
                                markup=False,
                            )
                    with Vertical(id="perf-footer"):
                        yield Static("", id="perf-legend")
                        yield DataTable(id="perf-table")
                        yield Static("", id="perf-summary")
                with TabPane("Table", id="tab-table"):
                    yield DataTable(id="perf-monthly-table")

    def on_mount(self) -> None:
        table = self.query_one("#perf-table", DataTable)
        table.cursor_type = "none"
        table.show_horizontal_scrollbar = False
        table.show_vertical_scrollbar = False
        monthly_dt = self.query_one("#perf-monthly-table", DataTable)
        monthly_dt.cursor_type = "none"
        monthly_dt.show_horizontal_scrollbar = True
        monthly_dt.show_vertical_scrollbar = True
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
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(0.15, self._on_resize_layout)

    def _on_resize_layout(self) -> None:
        if self._period_rows:
            self._populate_returns_table()
        if self._prices is not None:
            self._render_chart()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "perf-open-search":
            self.app.navigate_to("research-search")
        elif event.button.id == "perf-export":
            self._export()
        elif event.button.id == "perf-average-btn":
            self._show_average = not self._show_average
            self._update_average_button()
            if self._prices is not None:
                self._render_chart()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tab.id == "--content-tab-tab-table" and self._monthly_table is not None:
            self._populate_monthly_table()

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
        self.query_one("#perf-empty").display = False
        self.query_one("#perf-body").display = True
        self.query_one("#perf-title", Static).update(f"{self._ticker} — Seasonals")
        self.loading = True
        self.run_worker(self._load(self._ticker), exclusive=True)

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

    def _chart_container_width(self) -> int:
        """Available chart width in terminal cells."""
        try:
            container = self.query_one("#perf-chart-container")
            if container.size.width > 0:
                return container.size.width
            if container.region.width > 0:
                return container.region.width
        except Exception:
            pass
        view_w = self.size.width or 0
        if view_w < 40:
            try:
                view_w = self.app.size.width
            except Exception:
                view_w = 80
        return max(40, view_w - 4)

    def _chart_container_height(self) -> int:
        """Chart area height in terminal rows.

        #perf-chart-container collapses to the pinned image widget height
        (circular dependency), so we use #perf-chart-area as the primary
        source and fall back to the container only when the area reports zero.
        """
        try:
            area = self.query_one("#perf-chart-area")
            h = area.size.height if area.size.height > 0 else area.region.height
            if h > 0:
                return h
        except Exception:
            pass
        try:
            container = self.query_one("#perf-chart-container")
            height = container.size.height if container.size.height > 0 else container.region.height
            if height > 0:
                return height
        except Exception:
            pass
        return 0

    def _footer_height(self) -> int:
        """Footer band height in terminal rows (legend + table + summary)."""
        try:
            footer = self.query_one("#perf-footer")
            height = footer.size.height if footer.size.height > 0 else footer.region.height
            if height > 0:
                return height
        except Exception:
            pass
        return 9

    def _max_image_rows(self) -> int:
        """Cap sixel to chart area height.

        #perf-chart-container collapses to the image widget's pinned height
        (circular dependency), so we use #perf-chart-area as the authoritative
        source of available rows and fall back to the container only when the
        area reports zero.
        """
        try:
            area = self.query_one("#perf-chart-area")
            area_h = area.size.height if area.size.height > 0 else area.region.height
            if area_h > 0:
                return max(_MIN_CHART_ROWS, area_h - 1)
        except Exception:
            pass
        container_h = self._chart_container_height()
        if container_h > 0:
            return max(_MIN_CHART_ROWS, container_h - 1)
        return _MIN_CHART_ROWS

    def _chart_available_rows(self) -> int:
        """Chart height in terminal rows, leaving room for header, controls, and footer."""
        return self._max_image_rows()

    def _chart_cell_size(self) -> tuple[int, int]:
        """Chart area size in terminal cells (cols, rows), clamped to container."""
        cols = self._chart_container_width()
        rows = min(self._chart_available_rows(), self._max_image_rows())
        container_h = self._chart_container_height()
        if container_h > 0:
            rows = min(rows, container_h)
        return cols, max(_MIN_CHART_ROWS, rows)

    def _chart_pixel_size(self) -> tuple[int, int, int, int]:
        """Return (cols, rows, width_px, height_px) with supersampling."""
        cols, rows = self._chart_cell_size()
        return chart_pixel_dimensions(cols, rows, cell_size=terminal_cell_size(), apply_mins=False)

    def _apply_chart_widget_size(self, cols: int, rows: int) -> None:
        """Pin image widget to 1:1 cell mapping to avoid upscaling a small PNG."""
        widget = self._chart_image_widget()
        if widget is None:
            return
        try:
            container = self.query_one("#perf-chart-container")
            if container.size.width > 0:
                cols = min(cols, container.size.width)
        except Exception:
            pass
        container_h = self._chart_container_height()
        if container_h > 0:
            rows = min(rows, container_h)
        widget.styles.width = cols
        widget.styles.height = max(_MIN_CHART_ROWS, rows)

    def _chart_dimensions(self) -> tuple[int, int]:
        """Fit plotext canvas to available terminal width and height."""
        width = max(50, self._chart_container_width())
        return width, self._chart_available_rows()

    def _table_column_width(self, num_cols: int) -> int:
        """Equal column width so columns fit without horizontal scroll."""
        table = self.query_one("#perf-table", DataTable)
        width = table.size.width if table.size.width > 0 else table.region.width
        if width <= 0:
            width = max(40, (self.size.width or 0) - 4)
            if width < 40:
                try:
                    width = max(40, self.app.size.width - 4)
                except Exception:
                    width = 80
        pad = 2 * table.cell_padding
        usable = max(num_cols * 4, width - 1)
        return max(4, (usable - num_cols * pad) // num_cols)

    def _fit_return_cell(self, value: float | None, col_w: int) -> str:
        """Format a return for a fixed-width column, dropping decimals if needed."""
        from etfray.domain.overview_format import fmt_pct

        for decimals in (2, 1, 0):
            text = fmt_pct(value, signed=True, decimals=decimals)
            if len(text) <= col_w:
                return text
        text = fmt_pct(value, signed=True, decimals=0)
        return text[:col_w] if len(text) > col_w else text

    def _populate_returns_table(self) -> None:
        """Populate period returns as a single horizontal row."""
        from etfray.domain.seasonals_analytics import PERIOD_LABELS

        table = self.query_one("#perf-table", DataTable)
        returns_by_label = dict(self._period_rows)
        col_w = self._table_column_width(len(PERIOD_LABELS))
        table.clear(columns=True)
        for label in PERIOD_LABELS:
            table.add_column(label, key=label, width=col_w)
        table.add_row(*[self._fit_return_cell(returns_by_label.get(label), col_w) for label in PERIOD_LABELS])

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

    async def _load(self, ticker: str) -> None:
        from asyncio import to_thread

        from etfray.data.price_history_service import get_price_history, get_price_history_last_error
        from etfray.domain.overview_format import fmt_pct
        from etfray.domain.seasonals_analytics import (
            _adj_close_series,
            available_years,
            compute_period_returns,
            compute_summary,
        )

        df = await to_thread(get_price_history, ticker, "max")
        summary = self.query_one("#perf-summary", Static)

        self.loading = False

        if df is None or df.empty:
            err = get_price_history_last_error() or "No price history available"
            self.app.notify(err, severity="warning")
            self._populate_returns_table()
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

        # Override YTD with Yahoo's ytdReturn so it matches Home/Overview/Compare.
        # compute_period_returns uses auto-adjusted closes (total return incl. dividends)
        # which diverges from Yahoo's price-only ytdReturn convention.
        try:
            from etfray.data.market_data_service import get_etf_profile
            _profile = await to_thread(get_etf_profile, ticker)
            if _profile and _profile.ytd_return is not None:
                self._period_rows = [
                    (label, _profile.ytd_return if label == "YTD" else ret)
                    for label, ret in self._period_rows
                ]
        except Exception:
            pass
        self._available_years = available_years(self._prices)
        self._populate_year_selects()
        perf_summary = compute_summary(df)

        from etfray.domain.seasonals_analytics import compute_monthly_returns_table
        self._monthly_table = compute_monthly_returns_table(self._prices)

        self._populate_returns_table()

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

    def _redraw_footer(self) -> None:
        """Re-apply footer content after sixel chart draw (graphics can overwrite cells)."""
        if self._chart_render_cache is not None:
            series_list, average, _ = self._chart_render_cache
            self._update_legend(series_list, average)
        if self._period_rows:
            self._populate_returns_table()
        self._update_summary_chart_status()
        footer = self.query_one("#perf-footer")
        footer.refresh()
        for child in footer.children:
            child.refresh()

    def _update_legend(self, series_list: list, average) -> None:
        sorted_asc = sorted(series_list, key=lambda s: s.year)
        parts = []
        for s in sorted(series_list, key=lambda s: s.year, reverse=True):
            idx = next(i for i, x in enumerate(sorted_asc) if x.year == s.year)
            hex_color = color_for_series_index(idx)
            parts.append(f"[{hex_color}]■[/] {s.year} {_fmt_seasonal_pct(s.final_return_pct)}")
        if average is not None and average.day_of_year:
            parts.append(f"[bold white]--[/] Avg {_fmt_seasonal_pct(average.final_return_pct)}")
        self.query_one("#perf-legend", Static).update(_LEGEND_SEPARATOR.join(parts) if parts else "")

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
        img = PILImage.open(BytesIO(png))
        if img.size != (width_px, height_px):
            resample = getattr(PILImage, "Resampling", PILImage).LANCZOS
            img = img.resize((width_px, height_px), resample)
        widget.image = img
        self._apply_chart_widget_size(cols, rows)
        self._last_render_cells = (cols, rows)
        self._set_chart_mode("image")
        self._redraw_footer()
        self._update_summary_chart_status()
        if used_estimate:
            self._needs_layout_rerender = True
            self.call_after_refresh(self._finish_layout_rerender)

    def _render_chart(self) -> None:
        if self._prices is None or not self._year_start or not self._year_end:
            return

        from etfray.domain.seasonals_analytics import compute_seasonals

        series_list, average = compute_seasonals(
            self._prices,
            self._year_start,
            self._year_end,
            include_average=self._show_average,
        )
        if not series_list:
            self.app.notify("No seasonal data for selected years.", severity="warning")
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

    _MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

    def _populate_monthly_table(self) -> None:
        """Render the monthly returns heatmap into #perf-monthly-table."""
        tbl = self._monthly_table
        dt = self.query_one("#perf-monthly-table", DataTable)
        dt.clear(columns=True)

        if tbl is None or not tbl.years:
            dt.add_column("Status", width=40)
            dt.add_row("No monthly data available.")
            return

        col_width = 9

        dt.add_column("Date", width=6)
        for abbr in self._MONTH_ABBR:
            dt.add_column(abbr, width=col_width)
        dt.add_column("Year", width=col_width)

        def _fmt(val: float | None) -> str:
            if val is None:
                return "—"
            sign = "+" if val >= 0 else ""
            return f"{sign}{val * 100:.2f}%"

        def _cell(val: float | None) -> str:
            text = _fmt(val)
            if val is None:
                return text
            if val > 0:
                return f"[bold bright_green]{text}[/]"
            if val < 0:
                return f"[bold bright_red]{text}[/]"
            return text

        for year in tbl.years:
            months = tbl.monthly.get(year, {})
            row = [str(year)]
            for m in range(1, 13):
                row.append(_cell(months.get(m)))
            row.append(_cell(tbl.annual.get(year)))
            dt.add_row(*row)

        # Rises and falls footer row
        footer = ["[dim]Rises/falls[/]"]
        for m in range(1, 13):
            r = tbl.rises.get(m, 0)
            f = tbl.falls.get(m, 0)
            footer.append(f"[bright_green]▲{r}[/] [bright_red]▼{f}[/]")
        footer.append("")
        dt.add_row(*footer)

    def _update_average_button(self) -> None:
        btn = self.query_one("#perf-average-btn", Button)
        btn.set_class(self._show_average, "-on")

    def _export(self) -> None:
        if self._history_df is None or self._prices is None:
            self.app.notify("No data to export", severity="warning")
            return

        from etfray.data.export_service import export_dataframe_csv
        from etfray.db.database import load_settings
        from etfray.domain.seasonals_analytics import compute_seasonals, seasonals_to_export_rows

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
