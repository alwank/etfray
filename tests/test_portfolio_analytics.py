"""Tests for portfolio_analytics.calculate_lookthrough."""

import pandas as pd
import pytest

from etf_terminal.domain.portfolio_analytics import calculate_lookthrough


def _make_edgar_df(rows: list[dict]) -> pd.DataFrame:
    """Helper: create EDGAR-style DataFrame with value_usd."""
    return pd.DataFrame(rows)


def _make_zacks_df(rows: list[dict]) -> pd.DataFrame:
    """Helper: create Zacks-style DataFrame with pct_value."""
    return pd.DataFrame(rows)


class TestWeightNormalization:
    """Flaw 2/3: negative values and abs() normalization."""

    def test_negative_values_dont_inflate_weights(self):
        """EDGAR data with negative positions should not inflate positive holdings."""
        df = _make_edgar_df([
            {"ticker": "AAPL", "name": "Apple Inc", "value_usd": 500_000, "asset_category": "EC", "investment_country": "US"},
            {"ticker": "MSFT", "name": "Microsoft", "value_usd": 300_000, "asset_category": "EC", "investment_country": "US"},
            {"ticker": "", "name": "S&P500 FUTURE JUN26", "value_usd": -200_000, "asset_category": "DFE", "investment_country": "US"},
        ])
        positions = [{"symbol": "TEST", "weight": 100.0}]
        holdings_cache = {"TEST": df}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        # With abs() total = 1_000_000. AAPL = 500k/1M = 50%, effective = 100*50/100 = 50
        # Without abs() total = 600k. AAPL = 500k/600k = 83.3% — WRONG
        aapl = next(h for h in results if h.ticker == "AAPL")
        assert aapl.total_weight == pytest.approx(50.0, abs=0.1)

    def test_no_holding_exceeds_portfolio_weight(self):
        """No single holding should have effective weight > its source ETF's portfolio weight."""
        df = _make_edgar_df([
            {"ticker": "BOND", "name": "US Treasury", "value_usd": 1_000_000, "asset_category": "STIV", "investment_country": "US"},
            {"ticker": "", "name": "Futures Short", "value_usd": -800_000, "asset_category": "DFE", "investment_country": "US"},
        ])
        positions = [{"symbol": "DBMF", "weight": 10.0}]
        holdings_cache = {"DBMF": df}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        for h in results:
            assert h.total_weight <= 10.0


class TestAggregationKey:
    """Flaw 1/6: name-based key collision and truncation."""

    def test_different_names_not_merged(self):
        """Holdings with different full names should NOT be merged."""
        df_a = _make_zacks_df([
            {"ticker": "", "name": "TREASURY BILL", "pct_value": 5.0},
        ])
        df_b = _make_zacks_df([
            {"ticker": "", "name": "TREASURY BILL DUE 2026-03-15", "pct_value": 3.0},
        ])
        positions = [
            {"symbol": "ETF_A", "weight": 50.0},
            {"symbol": "ETF_B", "weight": 50.0},
        ]
        holdings_cache = {"ETF_A": df_a, "ETF_B": df_b}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        # Should be 2 separate holdings, not merged
        names = [h.name for h in results]
        assert "TREASURY BILL" in names
        assert "TREASURY BILL DUE 2026-03-15" in names

    def test_same_full_name_merged(self):
        """Holdings with identical full names across ETFs should be merged."""
        df_a = _make_zacks_df([
            {"ticker": "", "name": "State Street Navigator Securities", "pct_value": 2.0},
        ])
        df_b = _make_zacks_df([
            {"ticker": "", "name": "State Street Navigator Securities", "pct_value": 3.0},
        ])
        positions = [
            {"symbol": "ETF_A", "weight": 50.0},
            {"symbol": "ETF_B", "weight": 50.0},
        ]
        holdings_cache = {"ETF_A": df_a, "ETF_B": df_b}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        ss = [h for h in results if "State Street" in h.name]
        assert len(ss) == 1
        assert set(ss[0].source_etfs) == {"ETF_A", "ETF_B"}

    def test_same_ticker_merged(self):
        """Holdings with same ticker across ETFs should be merged."""
        df_a = _make_zacks_df([
            {"ticker": "AAPL", "name": "Apple Inc", "pct_value": 10.0},
        ])
        df_b = _make_zacks_df([
            {"ticker": "AAPL", "name": "Apple Inc.", "pct_value": 5.0},
        ])
        positions = [
            {"symbol": "ETF_A", "weight": 60.0},
            {"symbol": "ETF_B", "weight": 40.0},
        ]
        holdings_cache = {"ETF_A": df_a, "ETF_B": df_b}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        aapl = [h for h in results if h.ticker == "AAPL"]
        assert len(aapl) == 1
        # ETF_A: 60 * 10/100 = 6, ETF_B: 40 * 5/100 = 2, total = 8
        assert aapl[0].total_weight == pytest.approx(8.0, abs=0.1)
        assert set(aapl[0].source_etfs) == {"ETF_A", "ETF_B"}


class TestSelfDeduplication:
    """Flaw 5: ETF holding itself."""

    def test_etf_excludes_itself(self):
        """If an ETF's holdings list includes its own ticker, it should be excluded."""
        df = _make_zacks_df([
            {"ticker": "AAPL", "name": "Apple Inc", "pct_value": 50.0},
            {"ticker": "SCHD", "name": "Schwab US Dividend", "pct_value": 1.0},
            {"ticker": "MSFT", "name": "Microsoft", "pct_value": 49.0},
        ])
        positions = [{"symbol": "SCHD", "weight": 100.0}]
        holdings_cache = {"SCHD": df}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        tickers = [h.ticker for h in results]
        assert "SCHD" not in tickers
        assert "AAPL" in tickers
        assert "MSFT" in tickers


class TestUnresolved:
    """Edge cases for unresolved ETFs."""

    def test_missing_holdings_marked_unresolved(self):
        positions = [{"symbol": "XYZ", "weight": 15.0}]
        holdings_cache = {"XYZ": None}

        _, unresolved = calculate_lookthrough(positions, holdings_cache)

        assert len(unresolved) == 1
        assert unresolved[0].ticker == "XYZ"
        assert unresolved[0].portfolio_weight == 15.0

    def test_empty_df_marked_unresolved(self):
        positions = [{"symbol": "XYZ", "weight": 15.0}]
        holdings_cache = {"XYZ": pd.DataFrame()}

        _, unresolved = calculate_lookthrough(positions, holdings_cache)

        assert len(unresolved) == 1


class TestSTIVFiltering:
    """STIV (Short-Term Investment) holdings should be excluded from lookthrough."""

    def test_stiv_holdings_excluded(self):
        """Holdings with asset_category STIV should not appear in results."""
        df = _make_edgar_df([
            {"ticker": "AAPL", "name": "Apple Inc", "value_usd": 500_000, "asset_category": "EC", "investment_country": "US"},
            {"ticker": None, "name": "State Street Navigator Securities Lending Trust", "value_usd": 100_000, "asset_category": "STIV", "investment_country": "US"},
        ])
        positions = [{"symbol": "SPY", "weight": 100.0}]
        holdings_cache = {"SPY": df}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        names = [h.name for h in results]
        assert "State Street Navigator Securities Lending Trust" not in names
        assert len(results) == 1
        assert results[0].ticker == "AAPL"

    def test_nan_ticker_displayed_as_empty(self):
        """Holdings with NaN ticker should have empty string ticker, not 'NAN'."""
        df = _make_edgar_df([
            {"ticker": float("nan"), "name": "Some Bond", "value_usd": 200_000, "asset_category": "DBT", "investment_country": "US"},
        ])
        positions = [{"symbol": "BND", "weight": 100.0}]
        holdings_cache = {"BND": df}

        results, _ = calculate_lookthrough(positions, holdings_cache)

        assert len(results) == 1
        assert results[0].ticker == ""
        assert results[0].name == "Some Bond"
