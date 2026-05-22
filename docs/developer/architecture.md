# Architecture

## Package Structure

```
etfray/
├── app.py              # Main Textual app, sidebar, view routing
├── db/
│   └── database.py     # SQLite layer: settings, cache, watchlists, price history
├── data/
│   ├── edgar_service.py        # EDGAR/EdgarTools integration
│   ├── ibkr_service.py         # IBKR TWS API connection
│   ├── web_service.py          # Alternative web holdings scraper
│   ├── sector_service.py       # Sector classification
│   ├── source_resolver.py      # Data source selection logic
│   ├── market_data_service.py  # Yahoo Finance fund profile (yfinance)
│   ├── price_history_service.py # Yahoo Finance OHLCV price history (yfinance)
│   └── export_service.py       # CSV/JSON export
├── domain/
│   ├── etf_analytics.py        # ETF-level computations (concentration, exposure, overlap)
│   ├── overview_format.py      # Overview view formatting (combines EDGAR + Yahoo data)
│   ├── seasonals_analytics.py  # Period returns, seasonal curves, year splitting
│   ├── seasonals_plot.py       # Chart rendering: matplotlib PNG or plotext ASCII
│   └── portfolio_analytics.py  # Portfolio-level computations (lookthrough, concentration)
└── ui/
    ├── splash_screen.py    # Startup splash: DB init, settings, IBKR connect, cache warmup
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
                                              │
IBKR TWS API ──────→ ibkr_service ───────────┤
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
| `market_data_service` | Yahoo Finance | Fund profile (category, expense ratio, beta, etc.) | 7 days |
| `price_history_service` | Yahoo Finance | OHLCV price history | 24 hours |
| `sector_service` | Multiple | Sector classification for tickers | Indefinite |
| `ibkr_service` | IBKR TWS | Live positions, margin, account data | Real-time (no cache) |

## Key Design Decisions

- **Local-first**: All data cached in SQLite (`~/.etfray/data.db`). The app works offline after initial data fetch.
- **Source provenance**: Each data point tracks its source (EDGAR filing date, Yahoo fetch date, web scrape date) for trust and freshness.
- **Startup connection**: IBKR connects during the splash screen using saved settings; failures are shown on splash and the app continues.
- **Separation of concerns**: `data/` handles I/O and caching, `domain/` handles computation and formatting, `ui/` handles presentation.
- **Graceful degradation**: Features work with partial data. If Yahoo is unavailable, Overview still shows EDGAR data. If `[charts]` isn't installed, Seasonals uses plotext ASCII.
- **Multiple data sources**: Holdings can come from EDGAR or web scraper. The `source_resolver` picks the best available based on freshness and user preference.
