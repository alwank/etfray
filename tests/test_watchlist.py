"""Tests for watchlist database operations and analytics integration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from etfray.domain.etf_analytics import calculate_concentration, calculate_weight_overlap


class TestWatchlistDB:
    """Test watchlist CRUD operations."""

    def setup_method(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._patcher = patch("etfray.db.database.DB_PATH", Path(self._tmp.name))
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_add_and_get_watchlist(self):
        from etfray.db.database import add_to_watchlist, get_watchlist

        add_to_watchlist("default", "VTI")
        add_to_watchlist("default", "SCHB")
        result = get_watchlist("default")
        assert "VTI" in result
        assert "SCHB" in result

    def test_add_duplicate_is_idempotent(self):
        from etfray.db.database import add_to_watchlist, get_watchlist

        assert add_to_watchlist("default", "VTI") is True
        assert add_to_watchlist("default", "VTI") is False
        result = get_watchlist("default")
        assert result.count("VTI") == 1

    def test_is_in_watchlist(self):
        from etfray.db.database import add_to_watchlist, is_in_watchlist

        assert is_in_watchlist("default", "VTI") is False
        add_to_watchlist("default", "VTI")
        assert is_in_watchlist("default", "VTI") is True
        assert is_in_watchlist("default", "SCHB") is False

    def test_remove_from_watchlist(self):
        from etfray.db.database import add_to_watchlist, get_watchlist, remove_from_watchlist

        add_to_watchlist("default", "VTI")
        add_to_watchlist("default", "SCHB")
        remove_from_watchlist("default", "VTI")
        result = get_watchlist("default")
        assert "VTI" not in result
        assert "SCHB" in result

    def test_empty_watchlist(self):
        from etfray.db.database import get_watchlist

        result = get_watchlist("default")
        assert result == []


class TestWatchlistMetrics:
    """Test concentration and overlap calculations used by watchlist."""

    def _make_df(self, tickers_weights: list[tuple[str, float]]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "ticker": [t for t, _ in tickers_weights],
                "name": [f"Company {t}" for t, _ in tickers_weights],
                "pct_value": [w for _, w in tickers_weights],
            }
        )

    def test_concentration_metrics(self):
        data = [(f"T{i}", 100 - i * 2) for i in range(20)]
        df = self._make_df(data)
        conc = calculate_concentration(df)
        assert conc.num_holdings == 20
        assert conc.top1_weight > 0
        assert conc.top10_weight > conc.top1_weight
        assert conc.effective_n > 0
        assert conc.largest_holding != ""

    def test_overlap_identical_funds(self):
        df = self._make_df([("AAPL", 30), ("MSFT", 25), ("GOOG", 20), ("AMZN", 15), ("META", 10)])
        overlap = calculate_weight_overlap(df, df)
        assert overlap == pytest.approx(100.0, abs=0.1)

    def test_overlap_no_shared_holdings(self):
        df_a = self._make_df([("AAPL", 50), ("MSFT", 50)])
        df_b = self._make_df([("XOM", 50), ("CVX", 50)])
        overlap = calculate_weight_overlap(df_a, df_b)
        assert overlap == 0.0

    def test_overlap_partial(self):
        df_a = self._make_df([("AAPL", 50), ("MSFT", 30), ("GOOG", 20)])
        df_b = self._make_df([("AAPL", 40), ("AMZN", 35), ("GOOG", 25)])
        overlap = calculate_weight_overlap(df_a, df_b)
        assert 0 < overlap < 100
