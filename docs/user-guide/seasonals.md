# Seasonals

The Seasonals view provides a TradingView-style seasonals chart showing year-over-year cumulative returns, alongside a period returns table for standard intervals.

**Access:** Press `t` from any research view, or navigate to **Research → Seasonals** in the sidebar.

![Seasonals view](../assets/Seasonals.png){ width="700" }

## What It Shows

The Seasonals view has two components:

1. **Seasonals chart** — Each line represents one calendar year's cumulative return from January 1st (0% baseline). This reveals seasonal patterns: when the ETF tends to rally or pull back within a year.
2. **Period returns table** — Total returns for standard intervals (1W, 1M, 3M, 6M, YTD, 1Y, 3Y, 5Y, Max).

## Chart Modes

etfray supports two chart rendering modes:

| Mode | Requires | Quality |
|------|----------|---------|
| **matplotlib image** | `pip install etfray[charts]` + terminal image support | High-resolution PNG rendered inline |
| **plotext ASCII** | Nothing extra (included by default) | Text-based chart using Unicode block characters |

The active mode is shown in the Seasonals summary line (e.g., `Chart: image (matplotlib)` or `Chart: text (plotext)`).

### Installing chart support

```bash
pip install etfray[charts]
```

This installs `matplotlib` and `textual-image`. Verify with:

```bash
python scripts/check_charts.py
```

Expected output for full support:

```
Chart: image (matplotlib)
charts_available: True
protocol: sixel  (or tgp, iterm2)
```

### Terminal image support

For the matplotlib chart to render as a crisp image (not blocky ASCII), your terminal must support an image protocol:

| Terminal | Protocol | Setup |
|----------|----------|-------|
| iTerm2 | iterm2 | Works out of the box |
| Kitty | kitty | Works out of the box |
| WezTerm | sixel | Works out of the box |
| VS Code / Cursor | sixel | Enable `terminal.integrated.enableImages` in settings, restart terminal |
| Windows Terminal 1.22+ | sixel | Works out of the box |

Without image support, etfray falls back to plotext ASCII rendering automatically.

## Year Range Selection

Use the **Year Start** and **Year End** dropdowns to select which years to display on the chart. Each selected year gets its own colored line showing that year's cumulative return trajectory.

**Tips:**

- Select 3–5 years for a readable comparison
- Include the current year to see how this year compares to historical patterns
- The **Average** toggle shows the mean cumulative return across all selected years

## Period Returns Table

The table below the chart shows total returns for standard periods:

| Period | Meaning |
|--------|---------|
| 1W | Last 7 calendar days |
| 1M | Last 1 month |
| 3M | Last 3 months |
| 6M | Last 6 months |
| YTD | Year-to-date (from January 1) |
| 1Y | Last 12 months |
| 3Y | Last 3 years |
| 5Y | Last 5 years |
| Max | Since earliest available data |

Returns are calculated from adjusted close prices (accounting for splits and dividends).

!!! note
    Period returns require sufficient price history. If the ETF has less than 5 years of data, the 5Y return will show as N/A. The `Max` period always uses all available history.

## Data Source

Price history is fetched from Yahoo Finance via yfinance and cached locally in SQLite with a 24-hour TTL. On subsequent visits, the cached data loads instantly. After 24 hours, etfray fetches fresh data automatically.

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| "No price history" | Yahoo rate-limited or ticker not found | Wait a moment and retry; verify the ticker exists on Yahoo Finance |
| Blurry/blocky chart | Terminal lacks image protocol support | Use iTerm2, Kitty, or enable `terminal.integrated.enableImages` in VS Code/Cursor |
| `Chart: text (plotext)` | `[charts]` not installed | Run `pip install etfray[charts]` |
| `Chart: image (halfcell)` | Image protocol not detected | Check `python scripts/check_charts.py` for protocol; switch to a supported terminal |
| Missing recent year | Insufficient trading days | A year needs at least 2 trading days to appear in the chart |

## Keybinding

| Key | Action |
|-----|--------|
| `t` | Jump to Seasonals view (global) |
