"""Performance analytics — period returns, seasonals, and growth index."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from pandas import DateOffset

PERIOD_LABELS = ("1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "Max")
MIN_TRADING_DAYS_PER_YEAR = 2


@dataclass
class PerformanceSummary:
    start_date: str
    end_date: str
    latest_price: float | None
    total_return: float | None


@dataclass
class SeasonalYearSeries:
    year: int
    day_of_year: list[int]
    cumulative_pct: list[float]
    final_return_pct: float


def _adj_close_series(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
    col = "Adj Close" if "Adj Close" in df.columns else "Close"
    if col not in df.columns:
        return pd.Series(dtype=float)
    s = df[col].dropna().copy()
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    return s.sort_index()


def _return_between(
    prices: pd.Series,
    start: pd.Timestamp,
    *,
    require_full_window: bool = True,
) -> float | None:
    if prices.empty:
        return None
    end_price = float(prices.iloc[-1])
    end_ts = prices.index[-1]
    if start > end_ts:
        return None
    if require_full_window and prices.index[0] > start:
        return None
    subset = prices[prices.index >= start]
    if subset.empty:
        return None
    start_price = float(subset.iloc[0])
    if start_price == 0:
        return None
    return (end_price / start_price) - 1


def _period_start(end_ts: pd.Timestamp, label: str) -> pd.Timestamp:
    if label == "YTD":
        return pd.Timestamp(datetime(end_ts.year, 1, 1))
    if label == "Max":
        return end_ts  # placeholder; caller uses first price
    offsets = {
        "1W": DateOffset(days=7),
        "1M": DateOffset(months=1),
        "3M": DateOffset(months=3),
        "6M": DateOffset(months=6),
        "1Y": DateOffset(years=1),
        "3Y": DateOffset(years=3),
        "5Y": DateOffset(years=5),
    }
    return end_ts - offsets[label]


def compute_period_returns(df: pd.DataFrame) -> list[tuple[str, float | None]]:
    """Compute total returns for standard period labels."""
    prices = _adj_close_series(df)
    if prices.empty:
        return [(label, None) for label in PERIOD_LABELS]

    end_ts = prices.index[-1]
    rows: list[tuple[str, float | None]] = []

    for label in PERIOD_LABELS:
        if label == "Max":
            ret = _return_between(prices, prices.index[0], require_full_window=False)
        else:
            start = _period_start(end_ts, label)
            ret = _return_between(prices, start, require_full_window=True)
        rows.append((label, ret))

    return rows


def compute_cumulative_index(df: pd.DataFrame) -> list[float]:
    """Normalize adjusted close to growth index starting at 100."""
    prices = _adj_close_series(df)
    if prices.empty:
        return []
    base = float(prices.iloc[0])
    if base == 0:
        return []
    index = (prices / base) * 100
    return [float(v) for v in index.tolist()]


def compute_summary(df: pd.DataFrame) -> PerformanceSummary:
    """Summary stats for the loaded history slice."""
    prices = _adj_close_series(df)
    if prices.empty:
        return PerformanceSummary("", "", None, None)

    start_ts = prices.index[0]
    end_ts = prices.index[-1]
    start_price = float(prices.iloc[0])
    end_price = float(prices.iloc[-1])
    total_return = None
    if start_price != 0:
        total_return = (end_price / start_price) - 1

    return PerformanceSummary(
        start_date=start_ts.strftime("%Y-%m-%d"),
        end_date=end_ts.strftime("%Y-%m-%d"),
        latest_price=end_price,
        total_return=total_return,
    )


def split_prices_by_year(prices: pd.Series) -> dict[int, pd.Series]:
    """Group adjusted close prices by calendar year."""
    if prices.empty:
        return {}
    by_year: dict[int, pd.Series] = {}
    for year, group in prices.groupby(prices.index.year):
        series = group.sort_index()
        if len(series) >= MIN_TRADING_DAYS_PER_YEAR:
            by_year[int(year)] = series
    return by_year


def compute_seasonal_series(year_prices: pd.Series, year: int) -> SeasonalYearSeries:
    """Cumulative % return from the year's first trading day (0% baseline)."""
    first_price = float(year_prices.iloc[0])
    if first_price == 0:
        return SeasonalYearSeries(year, [], [], 0.0)

    cumulative = ((year_prices / first_price) - 1) * 100
    days = [int(ts.dayofyear) for ts in year_prices.index]
    values = [float(v) for v in cumulative.tolist()]
    final_return = values[-1] if values else 0.0
    return SeasonalYearSeries(year, days, values, final_return)


def available_years(prices: pd.Series) -> list[int]:
    """Years with enough trading days for a seasonal line."""
    return sorted(split_prices_by_year(prices).keys())


def compute_seasonals(
    prices: pd.Series,
    year_start: int,
    year_end: int,
    *,
    include_average: bool = False,
) -> tuple[list[SeasonalYearSeries], SeasonalYearSeries | None]:
    """Build seasonal curves for years in [year_start, year_end]."""
    if year_start > year_end:
        year_start, year_end = year_end, year_start

    by_year = split_prices_by_year(prices)
    series_list: list[SeasonalYearSeries] = []
    for year in sorted(by_year.keys()):
        if year_start <= year <= year_end:
            series_list.append(compute_seasonal_series(by_year[year], year))

    average: SeasonalYearSeries | None = None
    if include_average and series_list:
        average = _compute_average_seasonal(series_list)
    return series_list, average


def _compute_average_seasonal(series_list: list[SeasonalYearSeries]) -> SeasonalYearSeries:
    """Mean cumulative % return per day-of-year across selected years."""
    buckets: dict[int, list[float]] = {}
    for series in series_list:
        for day, value in zip(series.day_of_year, series.cumulative_pct, strict=True):
            buckets.setdefault(day, []).append(value)

    days = sorted(buckets.keys())
    avg_values = [sum(buckets[d]) / len(buckets[d]) for d in days]
    final_return = avg_values[-1] if avg_values else 0.0
    return SeasonalYearSeries(0, days, avg_values, final_return)


def seasonals_to_export_rows(series_list: list[SeasonalYearSeries], prices: pd.Series) -> pd.DataFrame:
    """Flatten seasonal curves for CSV export."""
    by_year = split_prices_by_year(prices)
    rows: list[dict] = []
    for series in series_list:
        if series.year == 0:
            continue
        year_prices = by_year.get(series.year)
        if year_prices is None:
            continue
        for day, pct in zip(series.day_of_year, series.cumulative_pct, strict=True):
            date_str = ""
            matches = year_prices.index[year_prices.index.dayofyear == day]
            if len(matches) > 0:
                date_str = matches[0].strftime("%Y-%m-%d")
            rows.append(
                {
                    "year": series.year,
                    "day_of_year": day,
                    "date": date_str,
                    "cumulative_pct": round(pct, 4),
                }
            )
    return pd.DataFrame(rows)
