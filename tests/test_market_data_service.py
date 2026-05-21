"""Tests for Yahoo Finance market data service and overview formatting."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from etfray.data.edgar_service import ETFReport
from etfray.data.market_data_service import (
    PROFILE_CACHE_TTL_DAYS,
    ETFProfile,
    _cache_is_fresh,
    _has_profile_fields,
    _merge_funds_data,
    _normalize_expense_ratio,
    _normalize_return,
    _normalize_yield,
    _parse_yahoo_info,
    get_etf_profile,
)
from etfray.domain.etf_analytics import ConcentrationMetrics, ExposureBreakdown
from etfray.domain.overview_format import format_overview_lines

SAMPLE_YAHOO_INFO = {
    "longName": "Vanguard Total Stock Market Index Fund ETF Shares",
    "shortName": "Vanguard Total Stock Market ETF",
    "longBusinessSummary": "The fund employs an indexing investment approach.",
    "category": "Large Blend",
    "fundFamily": "Vanguard",
    "fundInceptionDate": 974073600,
    "netExpenseRatio": 0.0003,
    "dividendYield": 0.0106,
    "beta3Year": 1.03,
    "ytdReturn": 0.0597418,
    "threeYearAverageReturn": 0.2222421,
    "fiveYearAverageReturn": 0.1268376,
    "totalAssets": 2202624327680,
    "fullExchangeName": "NYSEArca",
    "averageVolume": 4737335,
    "navPrice": 364.21,
    "legalType": "Exchange Traded Fund",
}


class TestMarketDataService:
    def setup_method(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._patcher = patch("etfray.db.database.DB_PATH", Path(self._tmp.name))
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_parse_yahoo_info_maps_fields(self):
        fetched_at = datetime.now().isoformat()
        profile = _parse_yahoo_info("VTI", SAMPLE_YAHOO_INFO, fetched_at)

        assert profile is not None
        assert profile.ticker == "VTI"
        assert profile.long_name == SAMPLE_YAHOO_INFO["longName"]
        assert profile.description == SAMPLE_YAHOO_INFO["longBusinessSummary"]
        assert profile.category == "Large Blend"
        assert profile.fund_family == "Vanguard"
        assert profile.inception_date == "2000-11-13"
        assert profile.expense_ratio == 0.0003
        assert profile.dividend_yield == 0.0106
        assert profile.beta == 1.03
        assert profile.exchange == "NYSEArca"
        assert profile.source == "yahoo"
        assert profile.fetched_at == fetched_at

    def test_parse_handles_missing_expense_ratio(self):
        info = dict(SAMPLE_YAHOO_INFO)
        del info["netExpenseRatio"]
        info["annualReportExpenseRatio"] = 0.0004

        profile = _parse_yahoo_info("VTI", info, datetime.now().isoformat())
        assert profile is not None
        assert profile.expense_ratio == 0.0004

    def test_inception_date_from_epoch(self):
        profile = _parse_yahoo_info("VTI", SAMPLE_YAHOO_INFO, datetime.now().isoformat())
        assert profile is not None
        assert profile.inception_date == "2000-11-13"

    def test_parse_accepts_short_name_only(self):
        info = {"shortName": "Vanguard S&P 500 ETF", "quoteType": "ETF"}
        profile = _parse_yahoo_info("VOO", info, datetime.now().isoformat())
        assert profile is not None
        assert profile.long_name == "Vanguard S&P 500 ETF"

    def test_merge_funds_data_fills_empty_info(self):
        funds = MagicMock()
        funds.description = "The fund tracks the S&P 500."
        funds.fund_overview = {"categoryName": "Large Blend", "family": "Vanguard", "legalType": "ETF"}
        funds.fund_operations = None

        merged = _merge_funds_data("VOO", {}, funds)
        assert _has_profile_fields(merged)
        assert merged["longBusinessSummary"] == "The fund tracks the S&P 500."
        assert merged["category"] == "Large Blend"
        assert merged["fundFamily"] == "Vanguard"

    def test_normalize_vwo_style_yahoo_fields(self):
        assert _normalize_expense_ratio(0.06) == 0.0006
        assert _normalize_expense_ratio(0.0003) == 0.0003
        assert _normalize_yield(2.48, 0.0248) == 0.0248
        assert _normalize_return(9.09769) == pytest.approx(0.0909769)
        assert _normalize_return(0.1737282) == pytest.approx(0.1737282)

    def test_parse_vwo_style_info(self):
        info = {
            "longName": "Vanguard Emerging Markets Stock Index Fund",
            "shortName": "Vanguard FTSE Emerging Markets",
            "longBusinessSummary": "Emerging markets index fund.",
            "category": "Diversified Emerging Mkts",
            "netExpenseRatio": 0.06,
            "dividendYield": 2.48,
            "yield": 0.0248,
            "ytdReturn": 9.09769,
            "threeYearAverageReturn": 0.1737282,
        }
        profile = _parse_yahoo_info("VWO", info, datetime.now().isoformat())
        assert profile is not None
        assert profile.expense_ratio == 0.0006
        assert profile.dividend_yield == 0.0248
        assert profile.ytd_return == pytest.approx(0.0909769)

    @patch("yfinance.Ticker")
    def test_cache_hit_skips_fetch(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = SAMPLE_YAHOO_INFO
        mock_ticker.info = SAMPLE_YAHOO_INFO
        mock_ticker_cls.return_value = mock_ticker

        first = get_etf_profile("VTI")
        second = get_etf_profile("VTI")

        assert first is not None
        assert second is not None
        assert second.description == first.description
        mock_ticker_cls.assert_called_once_with("VTI")

    @patch("etfray.data.market_data_service._fetch_from_yahoo")
    def test_cache_expired_refetches(self, mock_fetch):
        from etfray.db.database import cache_etf_profile

        stale_time = (datetime.now() - timedelta(days=PROFILE_CACHE_TTL_DAYS + 1)).isoformat()
        stale_profile = ETFProfile(
            ticker="VTI",
            long_name="Stale Name",
            fetched_at=stale_time,
        )
        cache_etf_profile("VTI", json.dumps(stale_profile.__dict__), stale_time)

        refreshed = ETFProfile(
            ticker="VTI",
            long_name="Fresh Name",
            category="Large Blend",
            fetched_at=datetime.now().isoformat(),
        )
        mock_fetch.return_value = refreshed

        result = get_etf_profile("VTI")
        assert result is not None
        assert result.long_name == "Fresh Name"
        mock_fetch.assert_called_once_with("VTI")

    @patch("yfinance.Ticker")
    def test_get_profile_returns_none_on_empty_info(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = {}
        mock_ticker.info = {}
        mock_ticker.funds_data = MagicMock(description="", fund_overview={}, fund_operations=None)
        mock_ticker_cls.return_value = mock_ticker

        profile = get_etf_profile("BAD")
        assert profile is None

        from etfray.db.database import get_cached_etf_profile

        assert get_cached_etf_profile("BAD") is None

    @patch("yfinance.Ticker")
    def test_get_profile_uses_funds_data_when_info_empty(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = {}
        funds = MagicMock()
        funds.description = "SPDR S&P 500 ETF Trust seeks investment results."
        funds.fund_overview = {"categoryName": "Large Blend", "family": "State Street"}
        funds.fund_operations = None
        mock_ticker.funds_data = funds
        mock_ticker_cls.return_value = mock_ticker

        profile = get_etf_profile("SPY")
        assert profile is not None
        assert "S&P 500" in profile.description
        assert profile.category == "Large Blend"

    def test_cache_is_fresh_respects_ttl(self):
        now = datetime(2025, 5, 21, 12, 0, 0)
        fresh = (now - timedelta(days=3)).isoformat()
        stale = (now - timedelta(days=PROFILE_CACHE_TTL_DAYS + 1)).isoformat()

        assert _cache_is_fresh(fresh, now=now) is True
        assert _cache_is_fresh(stale, now=now) is False


class TestOverviewFormat:
    def _sample_report(self) -> ETFReport:
        return ETFReport(
            ticker="VTI",
            fund_name="Vanguard Total Stock Market Index Fund ETF Shares",
            issuer="Vanguard",
            cik="123456",
            series_id="S000012345",
            total_assets=2_200_000_000_000,
            net_assets=2_200_000_000_000,
            num_holdings=3800,
            reporting_period="2025-03-31",
            filed_date="2025-05-01",
        )

    def _sample_profile(self) -> ETFProfile:
        return ETFProfile(
            ticker="VTI",
            long_name="Vanguard Total Stock Market Index Fund ETF Shares",
            description="The fund employs an indexing investment approach.",
            category="Large Blend",
            fund_family="Vanguard",
            inception_date="2000-11-13",
            expense_ratio=0.0003,
            dividend_yield=0.0106,
            beta=1.03,
            ytd_return=0.0597418,
            return_3y=0.2222421,
            return_5y=0.1268376,
            exchange="NYSEArca",
            avg_volume=4_737_335,
            nav_price=364.21,
            fetched_at="2025-05-21T10:00:00",
        )

    def test_format_overview_lines_with_both_sources(self):
        concentration = ConcentrationMetrics(
            num_holdings=3800,
            top1_weight=7.5,
            top5_weight=25.0,
            top10_weight=28.4,
            top25_weight=45.0,
            top50_weight=60.0,
            largest_holding="AAPL",
            hhi=0.02,
            effective_n=50,
            verdict="Moderate",
        )
        top_sector = ExposureBreakdown(category="Technology", weight=31.0, count=120)

        lines = format_overview_lines(
            "VTI",
            self._sample_report(),
            self._sample_profile(),
            concentration,
            top_sector,
            None,
        )
        text = "\n".join(lines)

        assert "VTI — Vanguard Total Stock Market Index Fund ETF Shares" in text
        assert "Fund Profile (Yahoo Finance)" in text
        assert "Large Blend" in text
        assert "The fund employs an indexing investment approach." in text
        assert "Key Metrics (SEC N-PORT)" in text
        assert "Portfolio Shape (computed)" in text
        assert "Top 10 Weight:   28.4%" in text
        assert "Largest Sector:  Technology (31.0%)" in text
        assert "Profile Source:  Yahoo Finance (cached 2025-05-21)" in text

    def test_format_overview_profile_only_fallback(self):
        lines = format_overview_lines(
            "VTI",
            None,
            self._sample_profile(),
            None,
            None,
            None,
        )
        text = "\n".join(lines)

        assert "Fund Profile (Yahoo Finance)" in text
        assert "N-PORT data unavailable." in text
        assert "Key Metrics (SEC N-PORT)" in text
