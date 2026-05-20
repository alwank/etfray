# Architecture

## Package Structure

```
etfray/
├── app.py              # Main Textual app, sidebar, view routing
├── db/
│   └── database.py     # SQLite layer: settings, cache, watchlists, notes
├── data/
│   ├── edgar_service.py    # EDGAR/EdgarTools integration
│   ├── ibkr_service.py     # IBKR TWS API connection
│   ├── web_service.py      # Alternative web holdings scraper
│   ├── sector_service.py   # Sector classification
│   ├── source_resolver.py  # Data source selection logic
│   └── export_service.py   # CSV/JSON export
├── domain/
│   ├── etf_analytics.py        # ETF-level computations
│   └── portfolio_analytics.py  # Portfolio-level computations (lookthrough, concentration)
└── ui/
    ├── splash_screen.py    # Onboarding splash
    ├── commands.py         # Command palette provider
    ├── research/           # Research workspace views
    ├── portfolio/          # Portfolio workspace views
    ├── workspace/          # Settings, exports
    └── components/         # Shared UI components
```

## Data Flow

```
EDGAR API / Web ──→ data services ──→ SQLite cache
                                            │
IBKR TWS API ──────→ ibkr_service ─────────┤
                                            ▼
                                    domain analytics
                                            │
                                            ▼
                                      UI views (Textual)
```

## Key Design Decisions

- **Local-first**: All data cached in SQLite. The app works offline after initial data fetch.
- **Source provenance**: Each data point tracks its source (EDGAR filing date, web fetch date) for trust.
- **Lazy connection**: IBKR connects only when portfolio views are accessed.
- **Separation of concerns**: `data/` handles I/O, `domain/` handles computation, `ui/` handles presentation.
