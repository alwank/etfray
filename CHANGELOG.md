# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
