"""Render TradingView-style seasonals charts (matplotlib or plotext fallback)."""

from __future__ import annotations

import functools
import importlib.util
import io

from etfray.domain.performance_analytics import SeasonalYearSeries

# Approximate day-of-year for the 1st of each month (non-leap year).
MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

SEASONAL_COLORS: tuple[str, ...] = (
    "#4C9FE6",
    "#55A868",
    "#C44E52",
    "#DD8452",
    "#8172B3",
    "#937860",
    "#DA8BC3",
    "#8C8C8C",
    "#CCB974",
    "#64B5CD",
)

MPL_FIGURE_FACE = "#1e1e1e"
MPL_AXES_FACE = "#1e1e1e"
MPL_AXES_EDGE = "#555555"
MPL_LABEL_COLOR = "#cccccc"
MPL_TICK_COLOR = "#aaaaaa"
MPL_GRID_COLOR = "#333333"
AVERAGE_COLOR = "#ffffff"
AVERAGE_ALPHA = 0.85
ZERO_LINE_COLOR = "#666666"

CHART_SCALE = 2
DEFAULT_CHART_ROWS = 28
MIN_CHART_WIDTH_PX = 640
MIN_CHART_HEIGHT_PX = 360


@functools.lru_cache(maxsize=1)
def charts_available() -> bool:
    """True when optional [charts] deps (matplotlib + textual-image) are installed."""
    return (
        importlib.util.find_spec("matplotlib") is not None
        and importlib.util.find_spec("textual_image") is not None
    )


def chart_deps_status() -> str:
    """Human-readable chart backend status for the summary line."""
    mpl = importlib.util.find_spec("matplotlib") is not None
    img = importlib.util.find_spec("textual_image") is not None
    if mpl and img:
        return "Chart: image (matplotlib)"
    if not mpl and not img:
        return "Chart: ASCII — pip install etfray[charts]"
    if not mpl:
        return "Chart: ASCII — missing matplotlib"
    return "Chart: ASCII — missing textual-image"


@functools.lru_cache(maxsize=1)
def terminal_cell_size() -> tuple[int, int]:
    """Terminal character cell size in pixels (width, height)."""
    try:
        from textual_image._terminal import get_cell_size

        size = get_cell_size()
        return max(1, int(size.width)), max(1, int(size.height))
    except Exception:
        return (10, 20)


@functools.lru_cache(maxsize=1)
def chart_render_protocol() -> str:
    """Best-effort terminal image protocol used by textual-image."""
    if importlib.util.find_spec("textual_image") is None:
        return "unavailable"
    import sys

    from textual_image.renderable import sixel, tgp

    is_tty = sys.__stdout__ is not None and sys.__stdout__.isatty()
    if not is_tty:
        return "unicode"
    if sixel.query_terminal_support():
        return "sixel"
    if tgp.query_terminal_support():
        return "tgp"
    return "halfcell"


def chart_image_status() -> str:
    """Summary status when the matplotlib image chart is active."""
    proto = chart_render_protocol()
    if proto in ("sixel", "tgp"):
        return f"Chart: image ({proto})"
    if proto == "halfcell":
        return "Chart: image (halfcell — use iTerm2/Kitty for sharper)"
    if proto == "unicode":
        return "Chart: image (unicode — low res; use iTerm2/Kitty)"
    return "Chart: image"


def chart_pixel_dimensions(
    cols: int,
    rows: int,
    *,
    scale: int = CHART_SCALE,
    cell_size: tuple[int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Return (cols, rows, width_px, height_px) for a chart area."""
    cell_w, cell_h = cell_size or terminal_cell_size()
    width_px = max(MIN_CHART_WIDTH_PX, int(cols * cell_w * scale))
    height_px = max(MIN_CHART_HEIGHT_PX, int(rows * cell_h * scale))
    return cols, rows, width_px, height_px


def color_for_series_index(index: int) -> str:
    """Hex color for the i-th year line (stable with sorted years)."""
    return SEASONAL_COLORS[index % len(SEASONAL_COLORS)]


def seasonal_ylim(
    series_list: list[SeasonalYearSeries],
    average: SeasonalYearSeries | None,
) -> tuple[float, float]:
    """Y-axis limits with padding for seasonals cumulative %."""
    values: list[float] = []
    for series in series_list:
        values.extend(series.cumulative_pct)
    if average is not None:
        values.extend(average.cumulative_pct)
    if not values:
        return (-5.0, 5.0)
    ymin, ymax = min(values), max(values)
    margin = max(2.0, (ymax - ymin) * 0.08)
    return ymin - margin, ymax + margin


def render_seasonals_figure(
    series_list: list[SeasonalYearSeries],
    average: SeasonalYearSeries | None,
    *,
    title: str,
    width_px: int,
    height_px: int,
    dpi: int = 150,
) -> bytes:
    """Build a seasonals plot as PNG bytes (requires matplotlib)."""
    if importlib.util.find_spec("matplotlib") is None:
        raise ImportError("matplotlib is required for render_seasonals_figure")

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter

    width_px = max(320, width_px)
    height_px = max(180, height_px)

    fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)

    fig.patch.set_facecolor(MPL_FIGURE_FACE)
    ax.set_facecolor(MPL_AXES_FACE)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color(MPL_AXES_EDGE)
    ax.tick_params(colors=MPL_TICK_COLOR, labelsize=9)
    ax.xaxis.label.set_color(MPL_LABEL_COLOR)
    ax.yaxis.label.set_color(MPL_LABEL_COLOR)
    ax.title.set_color(MPL_LABEL_COLOR)

    sorted_series = sorted(series_list, key=lambda s: s.year)
    for i, series in enumerate(sorted_series):
        if not series.day_of_year:
            continue
        ax.plot(
            series.day_of_year,
            series.cumulative_pct,
            color=color_for_series_index(i),
            linewidth=1.8,
            solid_capstyle="round",
        )

    if average is not None and average.day_of_year:
        ax.plot(
            average.day_of_year,
            average.cumulative_pct,
            color=AVERAGE_COLOR,
            linewidth=2.0,
            linestyle="--",
            alpha=AVERAGE_ALPHA,
        )

    ax.set_xlim(1, 366)
    ax.set_xticks(MONTH_TICKS)
    ax.set_xticklabels(MONTH_LABELS, fontsize=9)
    ax.set_xlabel("Month")
    ax.set_ylabel("Cumulative return (%)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ymin, ymax = seasonal_ylim(series_list, average)
    ax.set_ylim(ymin, ymax)
    ax.axhline(0, color=ZERO_LINE_COLOR, linewidth=0.8, zorder=0)
    ax.grid(True, axis="y", linestyle="-", linewidth=0.5, color=MPL_GRID_COLOR, alpha=0.6)
    ax.set_title(title, fontsize=10, pad=8)

    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        facecolor=fig.get_facecolor(),
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.15,
    )
    buf.seek(0)
    return buf.read()


def render_seasonals_chart(
    series_list: list[SeasonalYearSeries],
    average: SeasonalYearSeries | None,
    *,
    width: int = 100,
    height: int = 22,
) -> str:
    """Build a multi-line seasonals plot as a terminal string (plotext fallback)."""
    import plotext as plt

    width = max(60, width)
    height = max(12, height)

    plt.clear_figure()
    plt.theme("dark")
    plt.plot_size(width, height)

    for series in series_list:
        if not series.day_of_year:
            continue
        plt.plot(series.day_of_year, series.cumulative_pct)

    if average is not None and average.day_of_year:
        plt.plot(average.day_of_year, average.cumulative_pct, style="dashed")

    plt.xticks(MONTH_TICKS, MONTH_LABELS)
    plt.xlim(1, 366)
    plt.xlabel("Month")
    plt.ylabel("%")
    plt.grid(True, True)
    plt.frame(True)
    plt.hline(0)

    return plt.uncolorize(plt.build()).strip()
