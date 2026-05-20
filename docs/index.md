# etfray

![etfray](assets/Hero.jpeg){ width="700" }

A terminal-based ETF research and portfolio analytics application built with [Textual](https://textual.textualize.io/).

etfray converts SEC fund filings and IBKR portfolio data into holdings, exposure, concentration, margin, and risk workflows — all from your terminal.

## Why etfray?

- **No cloud accounts** — No sign-ups, no API keys, no third-party dashboards. Your data stays on your machine.
- **No subscriptions** — ETF holdings data comes directly from SEC EDGAR filings. Free, authoritative, and always available.
- **Offline-capable** — All data cached locally in SQLite. After the first fetch, everything works without a network connection.
- **Keyboard-first** — Command palette, tree navigation, and keybindings. No mouse required.

## What can etfray do?

- **ETF Research** — Search thousands of ETFs, view holdings, sector/geographic exposure, concentration metrics, fees, risk, and SEC documents
- **Portfolio Analytics** — Connect to IBKR for live positions, lookthrough exposure (what your ETFs actually own), concentration analysis, and margin monitoring
- **Side-by-side Compare** — Compare multiple ETFs across holdings, exposure, overlap, and fees
- **Export** — Save any view to CSV or JSON for further analysis

## Get Started

<div class="grid cards" markdown>

- :material-download: **[Installation](getting-started/installation.md)**

    Install etfray from PyPI in one command

- :material-rocket-launch: **[Quick Start](getting-started/quickstart.md)**

    Launch the app and explore your first ETF in 2 minutes

- :material-connection: **[IBKR Setup](user-guide/ibkr-setup.md)**

    Connect to your IBKR account for portfolio analytics

</div>

## Learn by Example

| Tutorial | What you'll learn |
|----------|-------------------|
| [Research Workflow](tutorials/research-workflow.md) | Evaluate an ETF from search to export |
| [Portfolio Setup](tutorials/portfolio-setup.md) | Connect IBKR and explore your positions |
| [Overlap Analysis](tutorials/overlap-analysis.md) | Find hidden redundancy between ETFs |
| [Three-Fund Analysis](tutorials/three-fund-analysis.md) | Uncover concentration in a "diversified" portfolio |
| [Margin Monitoring](tutorials/margin-monitoring.md) | Set up early warnings for margin usage |

## Reference

- [User Guide](user-guide/etf-research.md) — Detailed explanation of every view and metric
- [Configuration](user-guide/configuration.md) — All settings with examples
- [Keybindings](user-guide/keybindings.md) — Keyboard shortcuts and workflows
- [Architecture](developer/architecture.md) — How etfray is built
