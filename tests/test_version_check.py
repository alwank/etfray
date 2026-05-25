"""Tests for PyPI version check and skip-until-next logic."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from etfray.version_check import (
    VersionCheckResult,
    fetch_latest_version,
    get_skipped_version,
    save_skipped_version,
    should_prompt_update,
    version_gt,
)


class TestVersionCompare:
    def test_version_gt(self):
        assert version_gt("1.1.0", "1.0.0")
        assert version_gt("1.0.10", "1.0.9")
        assert not version_gt("1.0.0", "1.0.0")
        assert not version_gt("1.0.0", "1.1.0")


class TestShouldPromptUpdate:
    def test_prompt_when_newer_and_not_skipped(self):
        assert should_prompt_update("1.0.0", "1.1.0", None)
        assert should_prompt_update("1.0.0", "1.1.0", "1.0.5")

    def test_no_prompt_when_up_to_date(self):
        assert not should_prompt_update("1.1.0", "1.1.0", None)
        assert not should_prompt_update("1.2.0", "1.1.0", None)

    def test_no_prompt_when_skipped_this_latest(self):
        assert not should_prompt_update("1.0.0", "1.1.0", "1.1.0")

    def test_prompt_again_when_newer_latest(self):
        assert should_prompt_update("1.0.0", "1.2.0", "1.1.0")


class TestFetchLatestVersion:
    def test_fetch_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"info": {"version": "9.9.9"}}
        mock_response.raise_for_status = MagicMock()

        with patch("etfray.version_check.httpx.get", return_value=mock_response) as mock_get:
            with patch("etfray.version_check.get_installed_version", return_value="1.0.0"):
                result = fetch_latest_version()

        mock_get.assert_called_once()
        assert result.installed == "1.0.0"
        assert result.latest == "9.9.9"
        assert result.error is None
        assert result.update_available

    def test_fetch_network_error(self):
        with patch("etfray.version_check.httpx.get", side_effect=httpx.TimeoutException("timeout")):
            with patch("etfray.version_check.get_installed_version", return_value="1.0.0"):
                result = fetch_latest_version()

        assert result.latest is None
        assert result.error is not None
        assert not result.update_available


class TestVersionSkipPersistence:
    def setup_method(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._patcher = patch("etfray.db.database.DB_PATH", Path(self._tmp.name))
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_save_and_get_skipped_version(self):
        assert get_skipped_version() is None
        save_skipped_version("1.1.0")
        assert get_skipped_version() == "1.1.0"
        save_skipped_version("1.2.0")
        assert get_skipped_version() == "1.2.0"


class TestVersionCheckResult:
    def test_update_available_false_on_error(self):
        r = VersionCheckResult(installed="1.0.0", error="offline")
        assert not r.update_available

    def test_update_available_false_when_same(self):
        with patch("etfray.version_check.version_gt", return_value=False):
            r = VersionCheckResult(installed="1.0.0", latest="1.0.0")
            assert not r.update_available
