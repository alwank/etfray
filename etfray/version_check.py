"""PyPI version check and optional in-place upgrade."""

from __future__ import annotations

import importlib.metadata
import logging
import subprocess
import sys
from dataclasses import dataclass

import httpx

_log = logging.getLogger(__name__)

PYPI_JSON_URL = "https://pypi.org/pypi/etfray/json"
PACKAGE_NAME = "etfray"
DEFAULT_TIMEOUT = 5.0


@dataclass
class VersionCheckResult:
    installed: str
    latest: str | None = None
    error: str | None = None

    @property
    def update_available(self) -> bool:
        if self.error or not self.latest:
            return False
        return version_gt(self.latest, self.installed)


def get_installed_version() -> str:
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        from etfray import __version__

        return __version__


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse semver-ish version into comparable integer tuple."""
    v = version.strip().lstrip("vV")
    parts: list[int] = []
    for segment in v.split("."):
        num = ""
        for ch in segment:
            if ch.isdigit():
                num += ch
            else:
                break
        if num:
            parts.append(int(num))
        else:
            break
    return tuple(parts) if parts else (0,)


def version_gt(a: str, b: str) -> bool:
    return _parse_version(a) > _parse_version(b)


def should_prompt_update(installed: str, latest: str, skipped_version: str | None) -> bool:
    if not version_gt(latest, installed):
        return False
    if skipped_version and skipped_version == latest:
        return False
    return True


def fetch_latest_version(timeout: float = DEFAULT_TIMEOUT) -> VersionCheckResult:
    installed = get_installed_version()
    try:
        r = httpx.get(PYPI_JSON_URL, timeout=timeout, follow_redirects=True)
        r.raise_for_status()
        latest = r.json()["info"]["version"]
        return VersionCheckResult(installed=installed, latest=latest)
    except Exception as e:
        _log.debug("version check failed: %s", e)
        return VersionCheckResult(installed=installed, error=str(e))


def get_skipped_version() -> str | None:
    from etfray.db.database import get_note

    note = get_note("system", "version_skip")
    if note and note.content.strip():
        return note.content.strip()
    return None


def save_skipped_version(latest: str) -> None:
    from etfray.db.database import upsert_note

    upsert_note("system", "version_skip", latest)


def run_upgrade() -> tuple[bool, str]:
    """Run pip upgrade for etfray. Returns (success, message)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            return True, "Updated — restart etfray"
        detail = (proc.stderr or proc.stdout or "pip failed").strip()
        if len(detail) > 200:
            detail = detail[:197] + "..."
        return False, detail
    except subprocess.TimeoutExpired:
        return False, "Upgrade timed out"
    except Exception as e:
        return False, str(e)
