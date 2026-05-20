# ETF Research

The Research workspace lets you look up any ETF and explore its holdings, exposures, and risk characteristics using data from SEC EDGAR filings.

## Search

Navigate to **Research → Search** or use the command palette (`ctrl+p`). Enter a ticker symbol (e.g., `VTI`, `QQQM`, `AVUV`) to look up an ETF.

## Views

### Overview

Summary of the ETF: fund name, issuer, total assets, number of holdings, reporting period, and filing date.

### Holdings

Full holdings table from the most recent N-PORT filing. Shows ticker, name, weight, value, and shares for each position.

### Exposure

Sector and geographic exposure breakdown computed from underlying holdings.

### Concentration

Top-N holdings concentration analysis. Shows how much of the fund is concentrated in the largest positions (top 10, top 25, etc.).

### Fees

Expense ratio and fee information extracted from fund filings.

### Risk

Risk metrics including standard deviation, beta, and drawdown characteristics where available.

### Documents

Browse SEC filings (N-PORT, N-CSR, etc.) for the selected ETF.

### Compare

Side-by-side comparison of multiple ETFs across key metrics.

## Data Sources

etfray supports two data sources for holdings:

- **EDGAR (N-PORT)** — Official SEC filings via EdgarTools. Most accurate but may lag by up to 60 days.
- **Zacks** — Alternative source with more current data for some funds.

Configure the preferred source in Settings (`ctrl+,`) or let `auto` mode pick the best available.
