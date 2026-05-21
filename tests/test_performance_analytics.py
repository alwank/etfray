"""Tests for performance analytics."""

import pandas as pd
import pytest

from etfray.domain.performance_analytics import (
    PERIOD_LABELS,
    compute_cumulative_index,
    compute_period_returns,
    compute_summary,
)


def _make_history(start: str, days: int, daily_return: float = 0.001) -> pd.DataFrame:
    dates = pd.bdate_range(start=start, periods=days)
    prices = [100.0]
    for _ in range(1, len(dates)):
        prices.append(prices[-1] * (1 + daily_return))
    return pd.DataFrame({"Adj Close": prices}, index=dates)


class TestPerformanceAnalytics:
    def test_compute_cumulative_index_starts_at_100(self):
        df = _make_history("2024-01-02", 20)
        index = compute_cumulative_index(df)
        assert len(index) == 20
        assert index[0] == pytest.approx(100.0)
        assert index[-1] > 100.0

    def test_compute_period_returns_labels(self):
        df = _make_history("2015-01-02", 1300)
        rows = compute_period_returns(df)
        assert [label for label, _ in rows] == list(PERIOD_LABELS)
        rows_dict = dict(rows)
        assert rows_dict["1W"] is not None
        assert rows_dict["1Y"] is not None
        assert rows_dict["Max"] is not None

    def test_compute_period_returns_short_history(self):
        df = _make_history("2025-05-01", 5)
        rows = dict(compute_period_returns(df))
        assert rows["Max"] is not None
        assert rows["5Y"] is None
        assert rows["3Y"] is None

    def test_ytd_uses_calendar_year(self):
        df = _make_history("2024-06-01", 250)
        rows = dict(compute_period_returns(df))
        assert rows["YTD"] is not None

    def test_compute_summary(self):
        df = _make_history("2024-01-02", 30, daily_return=0.002)
        summary = compute_summary(df)
        assert summary.start_date == "2024-01-02"
        assert summary.end_date == df.index[-1].strftime("%Y-%m-%d")
        assert summary.latest_price is not None
        assert summary.total_return is not None
        assert summary.total_return > 0

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        assert compute_cumulative_index(df) == []
        rows = compute_period_returns(df)
        assert all(ret is None for _, ret in rows)
        summary = compute_summary(df)
        assert summary.latest_price is None
