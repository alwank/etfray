#!/usr/bin/env python3
"""Launch etfray with a fake PyPI update to exercise splash + version modal.

Usage (from repo root; requires Python 3.11+):
    python3.11 scripts/dev_test_version_modal.py

Reset skip state first if you already dismissed 1.0.0:
    python3.11 scripts/dev_test_version_modal.py --reset-skip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

# Repo root on path when run as script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from etfray.version_check import VersionCheckResult  # noqa: E402


def _fake_fetch_latest_version(timeout: float = 5.0) -> VersionCheckResult:
    return VersionCheckResult(installed="0.9.0", latest="1.0.0")


def _reset_skip() -> None:
    from etfray.db.database import get_db

    get_db().execute("DELETE FROM notes WHERE target_type = 'system' AND target_id = 'version_skip'")
    get_db().commit()
    print("Cleared version_skip from ~/.etfray/data.db")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset-skip",
        action="store_true",
        help="Clear skipped-version note, then exit (no UI)",
    )
    args = parser.parse_args()

    if args.reset_skip:
        _reset_skip()
        return

    print("Starting etfray with fake version: installed 0.9.0, PyPI latest 1.0.0")
    print("Expect: splash Version warn → update modal → Skip or Update Now")
    print("Quit app with q after testing.\n")

    with (
        patch("etfray.version_check.fetch_latest_version", _fake_fetch_latest_version),
        patch("etfray.version_check.get_skipped_version", return_value=None),
    ):
        from etfray.app import main as run_app

        run_app()


if __name__ == "__main__":
    main()
