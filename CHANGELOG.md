# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.0.0] - 2026-05-24

### Added

- **Home Dashboard** — Completely redesigned startup landing screen (`SnapshotView`) with four live panels:
  - **Benchmark Marquee** — Horizontally scrolling ticker showing YTD returns for SPY, QQQ, AGG, and GLD. Pauses on hover; Refresh button force-fetches fresh data.
  - **Watchlist Snapshot** — Compact table showing every watchlist ticker with Fund Name, YTD return, Top-10 Weight, Effective N, HHI, and Top Sector. Double-click any row to open that ETF's research view.
  - **ETF Movers Panel** — Top-5 daily gainers and losers sourced from Yahoo Finance screener (`most_actives`, `gainers`, `losers`). Includes a staleness indicator (shows "Last session · date" when market data is >24 hours old), a Refresh button, and double-click to open. Falls back to a seed-universe of 40+ well-known ETFs via `yf.download` when the screener returns too few results (e.g., outside market hours).
  - **Seasonal Spotlight Strip** — For each watchlist ticker, shows the current month's historical win rate (e.g., `↑9/15 yrs`) and MTD return in green/red, giving an at-a-glance seasonal context without opening the Seasonals view.
- **Recent / Quick-Jump** — Row of pill buttons on the Home screen for up to 5 last-visited ETF tickers, plus a "Search →" shortcut pill. Automatically updated as you navigate ETFs.
- **Screener service** (`etfray/data/screener_service.py`) — New data service powering the ETF Movers panel. Queries Yahoo Finance screener for `most_actives`, `gainers`, and `losers`, filters to ETF `quoteType` only, de-duplicates, and stores results in a new `screener_cache` SQLite table with a 1-hour TTL. Accepts a `force_refresh` flag. If fewer than 10 ETFs are returned by the screener (Tier-1), automatically falls back to a Tier-2 seed-universe batch download of 40+ well-known ETFs (broad equity, fixed income, commodities, international, sector, and leveraged). Exposes `get_etf_movers()` and `get_screener_last_error()`.
- **Stress Scenarios (Margin view)** — New section in the Portfolio Margin view simulates portfolio cushion after −10% and −20% shocks to gross position value. Shows the projected cushion percentage and whether each shock would breach the configured warning threshold.
- **Quick Keys footer on Home** — Inline keybinding reference shown directly on the Home screen listing all single-key shortcuts (`/`, `p`, `t`, `h`, `x`, `c`, `m`, `r`, `d`, `w`, `s`, `^I`, `q`).

### Changed

- **Portfolio Risk view** — Now includes two additional metrics: **Equity Exposure %** (percentage of lookthrough holdings classified as asset type `EC` or `Equity`) and **Data Coverage** rating (`Full` when all positions are resolved, `Partial` when most are, `Low` when fewer than half resolve). Risk Drivers list is now dynamic and only surfaces active issues.
- **Portfolio Concentration view** — Ticker normalization strips spaces and slashes before pairwise overlap comparison (e.g., `BRK B` and `BRK/B` both normalize to `BRKB`). Jaccard overlap between ETF pairs is now scored as **High** / **Medium** / **Low** based on the average pairwise overlap ratio across all position pairs.
- **Compare view** — Added **weight-adjusted overlap** column showing overlap percentage vs the first ticker for each additional ETF. Added **average 52-week return** column computed as the weighted average of the `week52_return` field from web-source holdings.
- **Settings view** — All configurable settings are now exposed in the in-app Settings UI. New fields added: `ibkr_host`, `ibkr_client_id`, `freshness_days_acceptable`, `cache_dir`, and `export_dir`. The `data_source` field now validates the entered value before saving.
- **Market data service** — Added `_sanitize_cached_profile()` that auto-corrects previously cached whole-percent YTD values on read (Yahoo Finance previously returned `9.09` for +9.09%; any cached `|ytd| > 5` is divided by 100 on load).
- **Database** — Added `screener_cache` table for the new screener service. Migrated `holdings_cache` from a single `ticker` primary key to a composite `(ticker, source)` primary key (non-destructive migration: old table is renamed, recreated, and data is re-imported). Renamed the `'zacks'` data source to `'web'` across all cached rows and settings.
- **Cache utilities** (`_cache_utils.py`) — Added shared helper functions supporting the new screener cache table.
- **Version** — Bumped from `0.2.1` to `1.0.0`. PyPI classifier updated from `3 - Alpha` to `5 - Production/Stable`.

## [0.2.1] - 2026-05-22

### Added

- **IBKR splash connection** — IBKR connects during the splash screen startup sequence for faster portfolio access.

### Changed

- **Contributing guidelines** — Consolidated into a single source of truth with Gitflow branching workflow, codebase orientation, and documentation contribution guidance.
- **Code formatting** — Cleaned up formatting and improved readability across multiple files.

## [0.2.0] - 2026-05-22

### Added

- **Seasonals view** — TradingView-style seasonals chart showing cumulative year-over-year returns with year range selection and average line toggle. Supports high-resolution matplotlib rendering (via optional `[charts]` dependency) with automatic fallback to plotext ASCII charts.
- **Period returns table** — Standard return periods (1W, 1M, 3M, 6M, YTD, 1Y, 3Y, 5Y, Max) displayed alongside the seasonals chart.
- **Watchlist dashboard** — Track ETFs with at-a-glance metrics including holdings count, top holding, top-10 weight, effective N, concentration verdict, top sectors, overlap vs portfolio, and data freshness. Supports search, filter by issuer, add/remove with undo (Ctrl+Z), double-click to open, and CSV export.
- **Fund metadata via Yahoo Finance** — Overview now shows category, inception date, expense ratio, dividend yield, beta (3Y), YTD/3Y/5Y returns, exchange, average volume, NAV, and fund description sourced from yfinance.
- **Price history service** — Yahoo Finance OHLCV data with local SQLite caching (24-hour TTL) and automatic retry logic.
- **`w` keybinding** — Press `w` from any ETF view to add the current ETF to the watchlist.
- **`t` keybinding** — Press `t` to jump directly to the Seasonals view.
- **`[charts]` optional dependency** — `pip install etfray[charts]` installs matplotlib and textual-image for high-resolution seasonals charts with sixel/kitty/iterm2 terminal graphics protocol support.

### Changed

- **Overview view** — Now combines SEC N-PORT filing data with Yahoo Finance fund profile for a richer summary including fund description, category, and performance metrics.
- **Architecture** — Added `market_data_service.py` (Yahoo fund profiles), `price_history_service.py` (Yahoo OHLCV), `seasonals_analytics.py` (period returns and seasonal curves), `seasonals_plot.py` (chart rendering), and `watchlist_view.py` (watchlist UI).
- **Data sources** — Yahoo Finance added as a third data source alongside EDGAR and web scraper for fund metadata and price history.

## [0.1.2] - 2026-05-21

### Changed

- Documentation improvements

## [0.1.0] - 2026-05-20

Initial release.
