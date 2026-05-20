# Configuration

All settings are stored in a local SQLite database at `~/.etfray/data.db` and can be changed via the Settings view (`ctrl+,`).

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `ibkr_host` | `127.0.0.1` | IBKR TWS/Gateway host |
| `ibkr_port` | `7497` | IBKR API socket port |
| `ibkr_client_id` | `1` | Client ID for IBKR connection |
| `edgar_identity` | *(empty)* | Email for SEC EDGAR API (required by SEC fair use policy) |
| `data_source` | `auto` | Holdings source: `auto`, `edgar`, or `zacks` |
| `freshness_days_fresh` | `30` | Days before cached data is considered stale |
| `freshness_days_acceptable` | `90` | Days before cached data is rejected |
| `margin_warning_cushion` | `0.15` | Margin cushion warning threshold (15%) |
| `leverage_warning` | `2.0` | Leverage ratio warning threshold |

## Data Storage

etfray stores all data locally:

- **Database**: `~/.etfray/data.db` — settings, ETF cache, holdings cache, watchlists, notes
- **Cache**: `~/.etfray/cache/` — temporary data files
- **Exports**: `~/.etfray/exports/` — CSV/JSON exports

## EDGAR Identity

The SEC requires a user-agent string for EDGAR API access. Set your email in Settings to comply with their [fair use policy](https://www.sec.gov/os/accessing-edgar-data).
