"""Tests for Yahoo Finance price history service."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from etfray.data._cache_utils import cache_is_fresh
from etfray.data.price_history_service import (
    PRICE_HISTORY_CACHE_TTL_HOURS,
    VALID_PERIODS,
    _normalize_history_df,
    get_price_history,
)


def _sample_history() -> pd.DataFrame:
    dates = pd.bdate_range(start="2024-01-02", periods=10)
    return pd.DataFrame({"Close": range(100, 110)}, index=dates)


class TestPriceHistoryService:
    def setup_method(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._patcher = patch("etfray.db.database.DB_PATH", Path(self._tmp.name))
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_normalize_history_df(self):
        df = _normalize_history_df(_sample_history())
        assert df is not None
        assert "Close" in df.columns

    def test_normalize_empty_returns_none(self):
        assert _normalize_history_df(pd.DataFrame()) is None

    def test_normalize_falls_back_to_close(self):
        dates = pd.bdate_range(start="2024-01-02", periods=5)
        df = pd.DataFrame({"Close": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=dates)
        out = _normalize_history_df(df)
        assert out is not None

    def test_cache_is_fresh_respects_ttl(self):
        now = datetime(2025, 5, 21, 12, 0, 0)
        fresh = (now - timedelta(hours=12)).isoformat()
        stale = (now - timedelta(hours=PRICE_HISTORY_CACHE_TTL_HOURS + 1)).isoformat()
        assert cache_is_fresh(fresh, ttl=timedelta(hours=PRICE_HISTORY_CACHE_TTL_HOURS), now=now) is True
        assert cache_is_fresh(stale, ttl=timedelta(hours=PRICE_HISTORY_CACHE_TTL_HOURS), now=now) is False

    @patch("yfinance.Ticker")
    def test_get_price_history_fetches_and_caches(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_history()
        mock_ticker_cls.return_value = mock_ticker

        first, _ = get_price_history("VTI", "1y")
        second, _ = get_price_history("VTI", "1y")

        assert first is not None
        assert second is not None
        assert len(first) == len(second)
        mock_ticker_cls.assert_called_once_with("VTI")
        mock_ticker.history.assert_called_once_with(period="1y", auto_adjust=True)

    @patch("yfinance.Ticker")
    def test_get_price_history_empty_sets_error(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        result, err = get_price_history("BAD", "1y", force_refresh=True)
        assert result is None
        assert err

    @patch("yfinance.Ticker")
    def test_invalid_period_defaults_to_max(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _sample_history()
        mock_ticker_cls.return_value = mock_ticker

        get_price_history("VTI", "invalid", force_refresh=True)
        mock_ticker.history.assert_called_with(period="max", auto_adjust=True)

    @patch("etfray.data.price_history_service._fetch_from_yahoo")
    def test_cache_expired_refetches(self, mock_fetch):
        from etfray.db.database import cache_price_history

        stale_time = (datetime.now() - timedelta(hours=PRICE_HISTORY_CACHE_TTL_HOURS + 1)).isoformat()
        stale_df = _sample_history()
        cache_price_history(
            "VTI",
            "1y",
            stale_df.to_json(orient="split", date_format="iso"),
            stale_time,
        )

        refreshed = _sample_history()
        refreshed["Close"] = refreshed["Close"] + 50
        mock_fetch.return_value = (refreshed, "")

        result, _ = get_price_history("VTI", "1y")
        assert result is not None
        assert int(result["Close"].iloc[0]) == 150
        mock_fetch.assert_called_once_with("VTI", "1y")

    def test_valid_periods(self):
        assert "1y" in VALID_PERIODS
        assert "max" in VALID_PERIODS
