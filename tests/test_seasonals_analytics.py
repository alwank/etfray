"""Tests for seasonal performance analytics and plot rendering."""

import pandas as pd
import pytest

from etfray.domain.seasonals_analytics import (
    _adj_close_series,
    available_years,
    compute_seasonal_series,
    compute_seasonals,
    split_prices_by_year,
)
from etfray.domain.seasonals_plot import (
    MPL_AXES_FACE,
    MPL_FIGURE_FACE,
    TERMINAL_BACKGROUND,
    chart_deps_status,
    chart_pixel_dimensions,
    chart_render_protocol,
    charts_available,
    render_seasonals_chart,
    render_seasonals_figure,
    seasonal_ylim,
)


def _make_multi_year_history() -> pd.DataFrame:
    frames = []
    for year, start_price in [(2023, 100.0), (2024, 110.0), (2025, 120.0)]:
        dates = pd.bdate_range(start=f"{year}-01-02", periods=60)
        prices = [start_price * (1 + 0.001 * i) for i in range(len(dates))]
        frames.append(pd.DataFrame({"Adj Close": prices}, index=dates))
    return pd.concat(frames)


class TestSeasonalsAnalytics:
    def test_split_prices_by_year(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        by_year = split_prices_by_year(prices)
        assert set(by_year.keys()) == {2023, 2024, 2025}

    def test_seasonal_series_starts_at_zero(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        by_year = split_prices_by_year(prices)
        series = compute_seasonal_series(by_year[2024], 2024)
        assert series.cumulative_pct[0] == pytest.approx(0.0)
        assert series.final_return_pct == pytest.approx(series.cumulative_pct[-1])

    def test_partial_current_year(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        by_year = split_prices_by_year(prices)
        series = compute_seasonal_series(by_year[2025], 2025)
        assert len(series.day_of_year) == len(by_year[2025])
        assert series.day_of_year[-1] == int(by_year[2025].index[-1].dayofyear)

    def test_year_range_filter(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        series_list, _ = compute_seasonals(prices, 2024, 2025)
        years = {s.year for s in series_list}
        assert years == {2024, 2025}

    def test_average_line_day_100(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        series_list, average = compute_seasonals(prices, 2023, 2025, include_average=True)
        assert average is not None
        assert average.year == 0
        if 100 in average.day_of_year:
            idx = average.day_of_year.index(100)
            avg_val = average.cumulative_pct[idx]
            year_vals = []
            for s in series_list:
                if 100 in s.day_of_year:
                    year_vals.append(s.cumulative_pct[s.day_of_year.index(100)])
            if len(year_vals) == len(series_list):
                assert avg_val == pytest.approx(sum(year_vals) / len(year_vals))

    def test_available_years(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        assert available_years(prices) == [2023, 2024, 2025]

    def test_render_seasonals_chart_smoke(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        series_list, average = compute_seasonals(prices, 2023, 2025, include_average=True)
        output = render_seasonals_chart(series_list, average, width=80, height=18)
        assert len(output) > 100
        assert "\x1b[" not in output
        assert "Month" in output or "┌" in output

    def test_seasonal_ylim_padding(self):
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        series_list, average = compute_seasonals(prices, 2023, 2025, include_average=True)
        ymin, ymax = seasonal_ylim(series_list, average)
        assert ymin < ymax
        assert ymax - ymin >= 4.0

    def test_seasonal_ylim_empty(self):
        ymin, ymax = seasonal_ylim([], None)
        assert ymin == -5.0
        assert ymax == 5.0

    @pytest.mark.charts
    def test_render_seasonals_figure_smoke(self):
        pytest.importorskip("matplotlib")
        df = _make_multi_year_history()
        prices = _adj_close_series(df)
        series_list, average = compute_seasonals(prices, 2023, 2025, include_average=True)
        png = render_seasonals_figure(
            series_list,
            average,
            title="TEST Seasonals",
            width_px=400,
            height_px=240,
        )
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 500

    def test_chart_background_matches_terminal(self):
        assert TERMINAL_BACKGROUND == "#121212"
        assert MPL_FIGURE_FACE == TERMINAL_BACKGROUND
        assert MPL_AXES_FACE == TERMINAL_BACKGROUND

    def test_charts_available_is_bool(self):
        assert isinstance(charts_available(), bool)

    def test_chart_deps_status_returns_string(self):
        status = chart_deps_status()
        assert isinstance(status, str)
        assert status.startswith("Chart:")

    def test_chart_pixel_dimensions_supersampling(self):
        cols, rows, width_px, height_px = chart_pixel_dimensions(
            50,
            20,
            scale=2,
            cell_size=(10, 20),
        )
        assert cols == 50
        assert rows == 20
        assert width_px == 50 * 10 * 2
        assert height_px == 20 * 20 * 2

    def test_chart_pixel_dimensions_minimums(self):
        _, _, width_px, height_px = chart_pixel_dimensions(10, 5, cell_size=(8, 8))
        assert width_px >= 640
        assert height_px >= 360

    def test_chart_render_protocol_returns_string(self):
        proto = chart_render_protocol()
        assert proto in ("sixel", "tgp", "halfcell", "unicode", "unavailable")
