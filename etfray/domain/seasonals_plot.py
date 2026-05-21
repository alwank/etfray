"""Render TradingView-style seasonals charts with plotext."""

from __future__ import annotations

from etfray.domain.performance_analytics import SeasonalYearSeries

# Approximate day-of-year for the 1st of each month (non-leap year).
MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def render_seasonals_chart(
    series_list: list[SeasonalYearSeries],
    average: SeasonalYearSeries | None,
    *,
    width: int = 100,
    height: int = 22,
) -> str:
    """Build a multi-line seasonals plot as a terminal string."""
    import plotext as plt

    width = max(60, width)
    height = max(12, height)

    plt.clear_figure()
    plt.theme("dark")
    plt.plot_size(width, height)

    for series in series_list:
        if not series.day_of_year:
            continue
        # No per-line labels — legend is rendered separately in the UI.
        plt.plot(series.day_of_year, series.cumulative_pct)

    if average is not None and average.day_of_year:
        plt.plot(average.day_of_year, average.cumulative_pct, style="dashed")

    plt.xticks(MONTH_TICKS, MONTH_LABELS)
    plt.xlim(1, 366)
    plt.xlabel("Month")
    plt.ylabel("%")
    plt.hline(0)

    # plotext emits ANSI; Textual Static parses "[" as Rich markup — strip colors.
    return plt.uncolorize(plt.build()).strip()
