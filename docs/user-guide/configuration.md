# Configuration

All settings are stored in a local SQLite database at `~/.etfray/data.db` and can be changed via **Workspace → Settings** in the sidebar (or use `ctrl+p` and type "Settings").

## First-Time Setup Checklist

When you first install etfray, configure these settings before doing anything else:

1. **Set your EDGAR identity** — Enter your email address. The SEC requires this for API access and will block requests without it.
2. **Verify IBKR port** — If you use IBKR, confirm the port matches your TWS/Gateway configuration (7497 for TWS paper, 4001 for Gateway).
3. **Choose data source** — The default `auto` mode works for most users. Press `s` in the app to cycle between auto → edgar → web.

## Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `ibkr_host` | `127.0.0.1` | IBKR TWS/Gateway host address |
| `ibkr_port` | `7497` | IBKR API socket port |
| `ibkr_client_id` | `1` | Client ID for the IBKR API connection (must be unique per connected client) |
| `edgar_identity` | *(empty)* | Email for SEC EDGAR API (required by SEC fair use policy) |
| `data_source` | `auto` | Holdings source: `auto`, `edgar`, or `web` |
| `freshness_days_fresh` | `30` | Days before cached data is no longer considered fresh (🟢) |
| `freshness_days_acceptable` | `90` | Days before cached data is considered stale and re-fetched (>90 days = 🔴 Stale) |
| `margin_warning_cushion` | `0.15` | Margin cushion warning threshold (15%) |
| `leverage_warning` | `2.0` | Leverage ratio warning threshold |
| `cache_dir` | `~/.etfray/cache` | Directory for SEC series/class lookup cache files |
| `export_dir` | `~/.etfray/exports` | Directory where CSV/JSON exports are saved |

## Example Configurations

All settings below are configured via **Workspace → Settings** in the sidebar. There is no config file — everything is stored in the SQLite database.

### Paper trading (default)

```
ibkr_host: 127.0.0.1
ibkr_port: 7497
ibkr_client_id: 1
```

TWS paper trading uses port 7497 by default. This is the safest way to test the IBKR connection.

### Live trading via IB Gateway

```
ibkr_host: 127.0.0.1
ibkr_port: 4001
ibkr_client_id: 1
```

IB Gateway uses port 4001 for live accounts. Gateway is lighter than TWS and better for always-on setups.

### Aggressive freshness (active trader)

```
freshness_days_fresh: 7
freshness_days_acceptable: 30
```

If you trade frequently and want the most current holdings data, tighten the freshness thresholds. This means etfray will re-fetch data more often, but you'll always see recent filings.

### Relaxed freshness (buy-and-hold)

```
freshness_days_fresh: 60
freshness_days_acceptable: 180
```

If you rarely change positions, quarterly data is fine. This reduces network requests and works better in offline scenarios.

### Conservative margin alerts

```
margin_warning_cushion: 0.25
leverage_warning: 1.5
```

If you want earlier warnings before approaching margin limits, raise the cushion threshold and lower the leverage threshold. A 25% cushion warning gives you more time to react.

## Data Source Logic

The `data_source` setting controls where etfray gets ETF holdings. Change it by pressing `s` in the app to cycle between modes:

| Value | Behavior |
|-------|----------|
| `auto` | Checks both cached sources, uses whichever is more recent. If nothing is cached, tries EDGAR first, then web. |
| `edgar` | Always uses SEC EDGAR N-PORT filings. Most authoritative but may lag up to 60 days. |
| `web` | Always uses the alternative web source. More current for some funds but less authoritative. |

**When to use `edgar`:** You want official SEC data and don't mind the quarterly lag. Best for long-term analysis.

**When to use `web`:** You need more current holdings (e.g., after a known rebalance) and accept that the data is scraped rather than filed.

**When to use `auto`:** You want the best of both worlds. This is the right choice for most users.

## Data Storage

etfray stores all data locally:

- **Database**: `~/.etfray/data.db` — settings, ETF cache, holdings cache, price history cache, screener cache, watchlists
- **Cache files**: `~/.etfray/cache/` — SEC series/class lookup data (configurable via `cache_dir` in Settings)
- **Exports**: `~/.etfray/exports/` — CSV/JSON exports (configurable via `export_dir` in Settings)

All data stays on your machine. Nothing is sent to external services (except EDGAR/web API requests to fetch holdings data).

## EDGAR Identity

The SEC requires a user-agent string for EDGAR API access. Set your email in Settings to comply with their [fair use policy](https://www.sec.gov/os/accessing-edgar-data).

!!! warning
    Without an EDGAR identity set, requests to the SEC API will be rate-limited or blocked. This is the most common cause of "no data found" errors for new users.
