# Architecture

## Package Structure

```
etfray/
├── app.py              # Main Textual app, sidebar, view routing
├── db/
│   └── database.py     # SQLite layer: settings, cache, watchlists, price history, screener cache
├── data/
│   ├── edgar_service.py        # EDGAR/EdgarTools integration
│   ├── ibkr_service.py         # IBKR TWS API connection
│   ├── web_service.py          # Alternative web holdings scraper
│   ├── sector_service.py       # Sector classification
│   ├── source_resolver.py      # Data source selection logic
│   ├── market_data_service.py  # Yahoo Finance fund profile (yfinance)
│   ├── price_history_service.py # Yahoo Finance OHLCV price history (yfinance)
│   ├── screener_service.py     # Yahoo Finance ETF day-movers screener (yfinance)
│   ├── export_service.py       # CSV/JSON export
│   └── _cache_utils.py         # Shared cache helper utilities
├── domain/
│   ├── etf_analytics.py        # ETF-level computations (concentration, exposure, overlap)
│   ├── overview_format.py      # Overview view formatting (combines EDGAR + Yahoo data)
│   ├── seasonals_analytics.py  # Period returns, seasonal curves, year splitting
│   ├── seasonals_plot.py       # Chart rendering: matplotlib PNG or plotext ASCII
│   └── portfolio_analytics.py  # Portfolio-level computations (lookthrough, concentration)
└── ui/
    ├── splash_screen.py    # Startup splash: DB init, settings, IBKR connect, cache warmup
    ├── snapshot_view.py    # Home Dashboard: benchmark marquee, movers, watchlist snapshot, seasonal spotlight
    ├── commands.py         # Command palette provider
    ├── research/           # Research workspace views
    │   ├── search_view.py
    │   ├── overview_view.py    # Fund profile (EDGAR + Yahoo)
    │   ├── seasonals_view.py   # Seasonals chart + period returns
    │   ├── holdings_view.py
    │   ├── exposure_view.py
    │   ├── concentration_view.py
    │   ├── fees_view.py
    │   ├── risk_view.py
    │   ├── documents_view.py
    │   └── compare_view.py
    ├── portfolio/          # Portfolio workspace views
    │   ├── overview_view.py
    │   ├── positions_view.py
    │   ├── lookthrough_view.py
    │   ├── exposure_view.py
    │   ├── concentration_view.py
    │   ├── margin_view.py
    │   └── risk_view.py
    ├── workspace/          # Workspace views
    │   ├── watchlist_view.py   # Watchlist dashboard with metrics
    │   ├── exports_view.py
    │   └── settings_view.py
    └── components/         # Shared UI components
```

## Data Flow

```
EDGAR API ──────────→ data services ──→ SQLite cache
Web Scraper ────────→ data services ──→ SQLite cache
Yahoo Finance ──────→ data services ──→ SQLite cache
  (profiles, OHLCV,                         │
   and screener)                             │
                                             │
IBKR TWS API ──────→ ibkr_service ──────────┤
                                             ▼
                                     domain analytics
                                             │
                                             ▼
                                       UI views (Textual)
```

### Data service responsibilities

| Service | Source | Data | Cache TTL |
|---------|--------|------|-----------|
| `edgar_service` | SEC EDGAR | Holdings, fund info, filings | Freshness-based (30/90 days) |
| `web_service` | Web scraper | Alternative holdings | Freshness-based (30/90 days) |
| `market_data_service` | Yahoo Finance | Fund profile (category, expense ratio, beta, etc.); auto-corrects whole-percent YTD values on read | 7 days |
| `price_history_service` | Yahoo Finance | OHLCV price history | 24 hours |
| `screener_service` | Yahoo Finance | ETF day gainers/losers via screener + seed-universe fallback | 1 hour |
| `sector_service` | Multiple | Sector classification for tickers | Indefinite |
| `ibkr_service` | IBKR TWS | Live positions, margin, account data | Real-time (no cache) |

## SQLite Database Schema (key tables)

| Table | Primary Key | Description |
|-------|-------------|-------------|
| `settings` | `key` | All app configuration key-value pairs |
| `etf_cache` | `ticker` | EDGAR fund metadata per ticker |
| `holdings_cache` | `(ticker, source)` | Holdings JSON per ticker and source (`edgar` or `web`). Composite key since v1.0.0; migrated from single `ticker` key. |
| `price_history_cache` | `(ticker, period)` | Yahoo Finance OHLCV data per ticker and period |
| `etf_profile_cache` | `ticker` | Yahoo Finance fund profile per ticker |
| `screener_cache` | `cache_key` | Yahoo Finance screener results (e.g., `etf_movers`) with 1-hour TTL. Added in v1.0.0. |
| `watchlist` | `(list_name, ticker)` | Watchlist memberships |
| `notes` | `(target_type, target_id)` | Free-form notes; used for `("system", "recent_etfs")` JSON list |

### Notable migrations (run automatically at startup)

1. **`holdings_cache` composite key** — If the table has a single `ticker` primary key (pre-v1.0.0), it is renamed to `holdings_cache_old`, recreated with `PRIMARY KEY (ticker, source)`, and the old data is re-imported.
2. **`'zacks'` → `'web'` source rename** — Any rows with `source = 'zacks'` are updated to `source = 'web'`, and the `data_source` setting is updated if it was set to `'zacks'`.

## Key Design Decisions

- **Local-first**: All data cached in SQLite (`~/.etfray/data.db`). The app works offline after initial data fetch.
- **Source provenance**: Each data point tracks its source (EDGAR filing date, Yahoo fetch date, web scrape date) for trust and freshness.
- **Startup connection**: IBKR connects during the splash screen using saved settings; failures are shown on splash and the app continues.
- **Separation of concerns**: `data/` handles I/O and caching, `domain/` handles computation and formatting, `ui/` handles presentation.
- **Graceful degradation**: Features work with partial data. If Yahoo is unavailable, Overview still shows EDGAR data. If `[charts]` isn't installed, Seasonals uses plotext ASCII. If the screener returns too few ETFs, the movers panel falls back to a seed universe.
- **Multiple data sources**: Holdings can come from EDGAR or web scraper. The `source_resolver` picks the best available based on freshness and user preference.
- **Ticker normalization**: Spaces and slashes are stripped from ticker symbols before overlap comparisons (e.g., `BRK B` = `BRK/B` = `BRKB`), ensuring the same underlying stock is not counted twice due to formatting differences across data sources.
- **Debounced navigation**: A 50ms debounce window on the `action_nav` binding prevents sixel terminal graphics from injecting spurious key events (e.g., ESC or single letters) that would trigger unintended navigation.
- **YTD sanitization**: `market_data_service` corrects previously cached whole-percent YTD values (Yahoo Finance changed their API response format; old caches stored `9.09` where `0.0909` was expected). Any `|ytd| > 5` in the cache is divided by 100 on read.
