# ETF Research

The Research workspace lets you look up any ETF and explore its holdings, exposures, and risk characteristics using data from SEC EDGAR filings.

## Search

Navigate to **Research → Search** or use the command palette (`ctrl+p`). Enter a ticker symbol (e.g., `VTI`, `QQQM`, `AVUV`) to look up an ETF.

!!! tip
    The command palette (`ctrl+p`) is the fastest way to search. Start typing a ticker and press Enter.

## Views

### Overview

Summary of the ETF: fund name, issuer, total assets, number of holdings, reporting period, and filing date.

Use this to quickly confirm you're looking at the right fund and to check how recent the data is. The filing date tells you when the fund last reported to the SEC.

### Holdings

Full holdings table from the most recent N-PORT filing. Shows ticker, name, weight, value, and shares for each position.

**Example:** For VTI (Vanguard Total Stock Market), you'll see ~3,700 holdings. The top positions are typically Apple (~6.5%), Microsoft (~6%), Nvidia (~5%), with a long tail of small-cap stocks below 0.01%.

!!! note
    Holdings reflect the most recent quarterly N-PORT filing, not today's actual holdings. There can be a lag of up to 60 days between the reporting period and when the filing appears on EDGAR.

### Exposure

Sector and geographic exposure breakdown computed from underlying holdings. Shows what percentage of the fund is allocated to each sector (Technology, Healthcare, Financials, etc.) and country.

**What to look for:**

- Sector tilts — A "total market" fund like VTI will roughly mirror the S&P 500 sector weights. A thematic fund like QQQM will be heavily tilted toward Technology.
- Geographic concentration — Most US-domiciled ETFs hold primarily US equities, but some (like VXUS) are entirely international.

### Concentration

Top-N holdings concentration analysis. Shows how much of the fund is concentrated in the largest positions.

**Metrics explained:**

| Metric | Meaning |
|--------|---------|
| Top 10 weight | Cumulative weight of the 10 largest holdings |
| Top 25 weight | Cumulative weight of the 25 largest holdings |
| HHI | Herfindahl-Hirschman Index — sum of squared weights (as fractions). Ranges from near 0 (perfectly diversified) to 1 (single holding) |
| Effective N | 1 / HHI — the "equivalent number of equal-weight holdings." A fund with effective N of 50 behaves like 50 equally-weighted stocks |
| Verdict | Interpretation based on effective N: **Broadly diversified** (>100), **Moderately concentrated** (30–100), **Highly concentrated** (<30) |

**Example interpretations:**

- **VTI** — ~3,700 holdings, effective N ~120, verdict "Broadly diversified." Despite having thousands of holdings, the cap-weighting means it behaves like ~120 equal stocks.
- **QQQ** — ~100 holdings, effective N ~30, verdict "Moderately concentrated." The Nasdaq-100 is more top-heavy than it appears.
- **XLE** — ~25 holdings, effective N ~10, verdict "Highly concentrated." Energy sector ETFs tend to be dominated by a few mega-caps.

### Fees

Expense ratio and fee information extracted from fund filings. Lower is generally better for long-term holding, but compare within the same category (e.g., US total market funds against each other, not against sector funds).

### Risk

Risk metrics including standard deviation, beta, and drawdown characteristics where available. These are computed from historical data when available in the filings.

### Documents

Browse SEC filings (N-PORT, N-CSR, etc.) for the selected ETF. Useful for verifying data or reading the fund's own commentary.

- **N-PORT** — Quarterly holdings report (this is where etfray gets holdings data)
- **N-CSR** — Semi-annual/annual shareholder report with commentary and financials

### Compare

Side-by-side comparison of multiple ETFs across key metrics. Use this to evaluate alternatives before making allocation decisions.

**Tips for effective comparison:**

- Compare funds in the same category (e.g., VTI vs ITOT vs SCHB for US total market)
- Look at concentration differences — two "similar" funds can have very different top-10 weights
- Check overlap percentage — high overlap means the funds are largely redundant

## Data Sources

etfray supports two data sources for holdings:

- **EDGAR (N-PORT)** — Official SEC filings via EdgarTools. Most accurate and authoritative, but filings are quarterly and may lag by up to 60 days after the reporting period.
- **Web** — Alternative web source with more current data for some funds. Less authoritative but useful when you need recent changes.

**How `auto` mode works:** etfray checks which cached source is more recent and uses that. If neither is cached, it tries EDGAR first, then falls back to web.

Configure the preferred source in Settings (Workspace → Settings in the sidebar) or let `auto` mode pick the best available.

!!! info "Data freshness indicators"
    etfray tracks when each data point was fetched and from which source. Data younger than 30 days is considered **fresh**, 30–90 days is **acceptable**, and older than 90 days is **stale** (will trigger a re-fetch on next access). These thresholds are configurable in Settings.
