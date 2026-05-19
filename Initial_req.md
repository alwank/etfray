Below is a full Product Requirements Document for the app as currently defined.

Product Requirements Document

ETF Portfolio Terminal

1. Product Summary

ETF Portfolio Terminal is a terminal-based ETF research and portfolio analytics application built with Textual, EDGAR / EdgarTools, and IBKR TWS / IB Gateway integration.

The product helps users understand:

What does this ETF hold?
What exposures am I buying?
How concentrated is the ETF?
What risks are embedded?
How do my ETF positions combine at the portfolio level?
How much margin/leverage risk do I have in IBKR?

The app should feel less like a filing browser and more like an ETF due diligence + portfolio risk analytics workstation.

2. Product Positioning

One-line description

A Textual-powered ETF research and portfolio analytics terminal that converts SEC fund filings and IBKR portfolio data into holdings, exposure, concentration, margin, and risk workflows.

Core value proposition

The app should not only answer:

What does VTI hold?

It should answer:

What do my ETFs make me own, how concentrated am I, and how does that interact with my IBKR margin account?

3. Target Users

Primary user

Self-directed investor or portfolio builder using IBKR, especially someone holding multiple ETFs and using margin.

Typical behavior:

Owns ETFs such as VTI, QQQM, VXUS, SGOV, AVUV, AVDV, DBMF, PDBC, GLDM, STIP, VGIT, VWO
Uses IBKR TWS / IB Gateway
Wants portfolio analytics beyond what broker UI provides
Cares about exposure, overlap, concentration, and leverage
Prefers power-user keyboard workflows

Secondary users

ETF researchers
Quant-oriented retail investors
Portfolio analysts
Open-source finance tool users
Terminal-first power users

4. Product Goals

Goals

The app must:

Provide ETF research based on holdings, exposure, fees, risk, and documents
Connect to IBKR TWS / IB Gateway for live account and position data
Compute ETF lookthrough exposure across the user’s portfolio
Show portfolio concentration at ETF and underlying holding level
Show margin and leverage analytics
Keep SEC filing types hidden behind user-friendly data categories
Preserve source provenance for trust
Support keyboard-first terminal workflows

Non-goals for MVP

The MVP should not:

Place trades
Generate automated buy/sell recommendations
Act as a full trading platform
Act as a tax reporting engine
Act as a dividend-income tracker
Act as a complete transaction journal
Replace TWS
Replace professional risk systems

Removed from scope:

Portfolio Income
Rebalance
Activity

5. Data Sources

5.1 SEC EDGAR / EdgarTools

Used for ETF and fund research data.

Primary use cases:

ETF filings
Fund documents
Holdings disclosures
Prospectus information
Risk disclosures
Fee disclosures
Voting records
Regulatory provenance

Important ETF/fund forms:

N-PORT / NPORT-P  → portfolio holdings and fund-level portfolio information
N-1A              → registration statement / prospectus information
497               → prospectus supplements
N-CSR             → shareholder reports
N-CEN             → annual fund census information
N-PX              → proxy voting record

Form N-PORT is relevant because registered funds report portfolio investment information through it, and third-party datasets commonly parse it into fund metadata and portfolio holdings objects.  ￼

5.2 IBKR TWS / IB Gateway

Used for user-specific portfolio analytics.

Primary use cases:

Current positions
Market value
Average cost
Account summary
Net liquidation value
Gross position value
Buying power
Initial margin
Maintenance margin
Excess liquidity
Cushion
SMA
Leverage

IBKR’s TWS API supports account summary subscriptions through reqAccountSummary, including fields such as NetLiquidation, BuyingPower, GrossPositionValue, InitMarginReq, MaintMarginReq, ExcessLiquidity, Cushion, SMA, and Leverage.  ￼

IBKR’s TWS API also supports position subscriptions through reqPositions, returning account, contract, position size, and average cost.  ￼

5.3 Optional Future Data Sources

These are not required for MVP but should be architecturally allowed:

ETF issuer daily holdings files
Market data provider for price/NAV/performance
Benchmark/index data
Distribution history provider
Factor exposure provider
Credit/duration data provider

Reason: EDGAR is official and auditable, but issuer websites may provide fresher daily ETF holdings than regulatory filings.

6. UX Principle

The app must use data-type navigation, not filing-type navigation.

Bad primary navigation:

N-PORT
N-1A
N-CEN
N-CSR
N-PX
497

Good primary navigation:

Overview
Holdings
Exposure
Concentration
Fees
Risk
Documents
Compare

Filing types should appear as source provenance, not as the user’s main workflow.

Example:

Source: Form N-PORT, period ended 2026-03-31, filed 2026-04-28
Source: Prospectus / N-1A amendment
Source: Form N-CSR shareholder report

7. Top-Level Information Architecture

ETF Portfolio Terminal
├── Research Mode
│   ├── ETF Search
│   ├── ETF Overview
│   ├── Holdings
│   ├── Exposure
│   ├── Concentration
│   ├── Fees
│   ├── Risk
│   ├── Documents
│   └── Compare
│
├── Portfolio Mode
│   ├── Overview
│   ├── Positions
│   ├── ETF Lookthrough
│   ├── Portfolio Exposure
│   ├── Concentration
│   ├── Margin
│   └── Risk
│
└── Workspace
    ├── Watchlists
    ├── Notes
    ├── Exports
    └── Settings

8. Global Layout

The app should use a persistent terminal shell.

┌──────────────────────────────────────────────────────────────┐
│ ETF Portfolio Terminal          IBKR: Connected | EDGAR: OK   │
├───────────────────┬──────────────────────────────────────────┤
│ Workspace         │ Main Panel                               │
│                   │                                          │
│ Research          │                                          │
│ - ETF Search      │                                          │
│ - Overview        │                                          │
│ - Holdings        │                                          │
│ - Exposure        │                                          │
│ - Concentration   │                                          │
│ - Fees            │                                          │
│ - Risk            │                                          │
│ - Documents       │                                          │
│ - Compare         │                                          │
│                   │                                          │
│ Portfolio         │                                          │
│ - Overview        │                                          │
│ - Positions       │                                          │
│ - ETF Lookthrough │                                          │
│ - Exposure        │                                          │
│ - Concentration   │                                          │
│ - Margin          │                                          │
│ - Risk            │                                          │
│                   │                                          │
│ Workspace         │                                          │
│ - Watchlists      │                                          │
│ - Notes           │                                          │
│ - Exports         │                                          │
│ - Settings        │                                          │
├───────────────────┴──────────────────────────────────────────┤
│ NetLiq $____ | Gross __x | Cushion __% | Holdings as of ____  │
└──────────────────────────────────────────────────────────────┘

Textual is suitable for this kind of terminal UI because it provides widgets such as tables and interactive terminal components; DataTable is especially relevant for holdings, positions, and comparison screens.  ￼

9. Navigation Requirements

9.1 Sidebar

The sidebar must show:

Research
- ETF Search
- Overview
- Holdings
- Exposure
- Concentration
- Fees
- Risk
- Documents
- Compare
Portfolio
- Overview
- Positions
- ETF Lookthrough
- Exposure
- Concentration
- Margin
- Risk
Workspace
- Watchlists
- Notes
- Exports
- Settings

9.2 Global Command Palette

The app should support a command palette.

Example commands:

open VTI
open QQQM
compare VTI ITOT SCHB
portfolio
positions
lookthrough
margin
risk
documents VTI
export holdings VTI csv
export portfolio markdown
refresh ibkr
refresh edgar VTI

9.3 Keyboard Shortcuts

Suggested shortcuts:

/        Global search
p        Portfolio overview
h        Holdings
x        Exposure
c        Concentration
m        Margin
r        Risk
d        Documents
o        Open selected item
e        Export
Esc      Back
q        Quit

10. Research Mode Requirements

10.1 ETF Search

Purpose

Help the user find an ETF by ticker, name, issuer, CIK, or strategy.

User questions answered

Can I find an ETF quickly?
Can I search by issuer or strategy?
Can I open the ETF research workspace?

Required inputs

Ticker
Fund name
Issuer
CIK
Asset class
Strategy keyword

Required UI

┌──────────────────────────────────────────────┐
│ Search ETF / fund / issuer / CIK             │
├────────┬──────────────────────┬──────────────┤
│ Ticker │ Fund Name            │ Issuer       │
├────────┼──────────────────────┼──────────────┤
│ VTI    │ Vanguard Total...    │ Vanguard     │
│ QQQM   │ Invesco NASDAQ...    │ Invesco      │
│ SCHD   │ Schwab US Dividend   │ Schwab       │
└────────┴──────────────────────┴──────────────┘

Functional requirements

Search by ticker
Search by fund name
Search by issuer
Open ETF Overview from selected result
Show data availability indicators

Data availability indicators

EDGAR filings available
Holdings available
Prospectus available
Portfolio-owned indicator

Example:

VTI  Vanguard Total Stock Market ETF  Owned  EDGAR OK  Holdings OK

10.2 ETF Overview

Purpose

Give the user a high-level snapshot of the ETF.

User questions answered

What is this fund?
What asset class does it represent?
What does it broadly invest in?
How fresh is the data?
Do I own it?

Required UI

┌────────────────────────────────────────────────────────────┐
│ VTI — Vanguard Total Stock Market ETF                      │
│ Issuer: Vanguard | Asset Class: Equity | Region: US         │
├────────────────────────────────────────────────────────────┤
│ AUM        Expense Ratio    Holdings     Yield     Inception│
│ $___       0.__%            ____         __%       YYYY     │
├────────────────────────────────────────────────────────────┤
│ Your Portfolio Context                                      │
│ Position: ___ shares | Market Value: $___ | Weight: __%     │
├────────────────────────────────────────────────────────────┤
│ Top Exposures                                               │
│ US Equity | Large Cap | Technology | Financials             │
├────────────────────────────────────────────────────────────┤
│ Latest Sources                                              │
│ Holdings: N-PORT / issuer data as of YYYY-MM-DD             │
│ Prospectus: latest document filed YYYY-MM-DD                │
└────────────────────────────────────────────────────────────┘

Functional requirements

Show ETF name, ticker, issuer
Show asset class and strategy classification
Show latest holdings date
Show expense ratio if available
Show number of holdings if available
Show top holdings preview
Show portfolio context if user owns the ETF
Show source provenance

10.3 Holdings

Purpose

Show the ETF’s underlying holdings.

User questions answered

What does the ETF hold?
What are the largest positions?
How much weight is in each holding?
Are there cash, derivatives, bonds, or other non-equity positions?

Required UI

┌─────────────────────────────────────────────────────────────┐
│ Holdings                                      As of YYYY-MM-DD│
├───────┬────────────────────────┬──────────┬────────┬────────┤
│ Ticker│ Name                   │ Weight % │ Value  │ Shares │
├───────┼────────────────────────┼──────────┼────────┼────────┤
│ AAPL  │ Apple Inc.             │ 5.91%    │ ...    │ ...    │
│ MSFT  │ Microsoft Corp.        │ 5.42%    │ ...    │ ...    │
│ NVDA  │ NVIDIA Corp.           │ 4.88%    │ ...    │ ...    │
└───────┴────────────────────────┴──────────┴────────┴────────┘

Required columns

Ticker / identifier
Security name
Weight
Market value
Quantity / shares
Asset type
Country
Sector
Currency
Source

Functional requirements

Sort by weight
Sort by market value
Filter by asset type
Filter by country
Filter by sector
Search holding name/ticker
Show top 10 / top 25 / top 50 / all
Export CSV
Open holding detail
Show source filing/document

Empty-state behavior

If holdings are unavailable:

Holdings are not currently available from the configured EDGAR/issuer source.
Show latest fund documents instead.

10.4 Exposure

Purpose

Translate raw holdings into investor-friendly exposures.

User questions answered

What sectors am I buying?
What countries am I exposed to?
Is this equity, bond, commodity, cash, or derivatives exposure?
What factor/style does the ETF represent?

Required exposure categories

For all ETFs:

Asset class
Country
Region
Currency
Issuer
Instrument type

For equity ETFs:

Sector
Industry
Market cap bucket
Style / factor

For bond ETFs:

Duration bucket
Maturity bucket
Credit quality
Issuer type
Currency
Country

For commodity ETFs:

Commodity type
Futures exposure
Collateral
Counterparty / swap exposure

Required UI

┌──────────────────────────────┬──────────────────────────────┐
│ Sector Exposure              │ Country Exposure             │
├──────────────────────────────┼──────────────────────────────┤
│ Technology        31.2%      │ United States      96.4%     │
│ Financials        12.8%      │ Canada              1.1%     │
│ Health Care       11.6%      │ Other               2.5%     │
└──────────────────────────────┴──────────────────────────────┘

Functional requirements

Aggregate holdings into exposure categories
Show percentage weights
Allow drilldown from exposure bucket to holdings
Show unclassified exposure bucket
Show source freshness
Export exposure table

10.5 Concentration

Purpose

Show whether the ETF is diversified or concentrated.

User questions answered

How concentrated is this ETF?
How much is in the top 10 holdings?
Is this ETF really diversified?
Is sector concentration high?

Required metrics

Number of holdings
Top 1 weight
Top 5 weight
Top 10 weight
Top 25 weight
Top 50 weight
Largest holding
Effective number of holdings
HHI concentration score
Sector concentration
Country concentration
Issuer concentration

Required UI

Concentration Summary
├── Number of holdings: ____
├── Largest holding: __%
├── Top 10 holdings: __%
├── Top 25 holdings: __%
├── Effective holdings: ____
├── HHI: Low / Medium / High
└── Verdict: Broadly diversified / moderately concentrated / highly concentrated

Functional requirements

Calculate concentration metrics
Show top holding concentration
Show sector concentration
Show country concentration
Show interpretation label
Allow export

10.6 Fees

Purpose

Show the cost of owning the ETF.

User questions answered

How expensive is this ETF?
What is the net expense ratio?
Are there waivers?
Are acquired fund fees relevant?

Required fields

Net expense ratio
Gross expense ratio
Fee waivers
Acquired fund fees
Management fee
Other expenses
Source document
Effective date

Required UI

┌────────────────────────────────────────────┐
│ Fees                                       │
├────────────────────────────────────────────┤
│ Net Expense Ratio:   0.__%                 │
│ Gross Expense Ratio: 0.__%                 │
│ Waiver:              Yes / No              │
├────────────────────────────────────────────┤
│ Source: Prospectus / N-1A / 497            │
└────────────────────────────────────────────┘

Functional requirements

Show fee data if available
Show fee source provenance
Display missing values clearly
Allow comparison against peer ETFs

10.7 Risk

Purpose

Summarize ETF-specific risks.

User questions answered

What can go wrong with this ETF?
Is the ETF exposed to concentration risk?
Does it have derivatives, credit, duration, currency, or liquidity risk?

Required risk categories

Market risk
Concentration risk
Liquidity risk
Tracking risk
Premium/discount risk
Derivatives risk
Currency risk
Credit risk
Duration risk
Commodity/futures risk
Securities lending risk

Required UI

Risk Summary
├── Market Risk: High
├── Concentration Risk: Medium
├── Liquidity Risk: Low
├── Derivatives Risk: None detected / Present
├── Tracking Risk: Medium
└── Source: Prospectus risk disclosures

Functional requirements

Show risk categories
Show source document
Show raw disclosure link/document view
Flag missing or stale risk data

10.8 Documents

Purpose

Provide source documents and audit trail.

User questions answered

Where did this data come from?
Can I inspect the source filing?
Can I open the latest prospectus or holdings report?

Required document categories

Prospectus
Summary Prospectus
Statement of Additional Information
Shareholder Reports
Annual/Semiannual Reports
Portfolio Holdings Reports
Proxy Voting Records
Raw SEC Filings

Required UI

┌───────────────┬────────────┬────────────┬────────────────────┐
│ Document Type │ Form       │ Filed Date │ Description        │
├───────────────┼────────────┼────────────┼────────────────────┤
│ Prospectus    │ N-1A / 497 │ YYYY-MM-DD │ Latest prospectus  │
│ Holdings      │ N-PORT     │ YYYY-MM-DD │ Portfolio report   │
│ Voting        │ N-PX       │ YYYY-MM-DD │ Proxy voting       │
└───────────────┴────────────┴────────────┴────────────────────┘

Functional requirements

List source documents
Filter by document type
Open document
Show filing date
Show period date
Show accession number
Export document metadata

10.9 Compare

Purpose

Compare ETFs side by side.

User questions answered

Which ETF is cheaper?
Which ETF is more concentrated?
How much holdings overlap exists?
Which ETF has better exposure for my use case?

Required comparison dimensions

Expense ratio
Number of holdings
Top 10 weight
Asset class
Region
Sector exposure
Country exposure
Holdings overlap
Largest holdings
Risk categories
Document freshness
Portfolio ownership status

Required UI

Compare: VTI vs ITOT vs SCHB
┌──────────────┬────────┬────────┬────────┐
│ Metric       │ VTI    │ ITOT   │ SCHB   │
├──────────────┼────────┼────────┼────────┤
│ Expense      │ 0.03%  │ 0.03%  │ 0.03%  │
│ Holdings     │ 3,600+ │ 2,500+ │ 2,400+ │
│ Top 10 Wt    │ __%    │ __%    │ __%    │
│ Owned        │ Yes    │ No     │ No     │
└──────────────┴────────┴────────┴────────┘

Functional requirements

Compare 2–5 ETFs
Show side-by-side metrics
Show overlap percentage
Show top overlapping holdings
Show exposure differences
Export comparison

11. Portfolio Mode Requirements

11.1 Portfolio Overview

Purpose

Show the current IBKR portfolio at a glance.

User questions answered

What do I own?
How much is my portfolio worth?
How levered am I?
How much margin cushion do I have?
Where are the biggest exposures?

Required UI

┌──────────────────────────────────────────────────────────────┐
│ Portfolio Overview                         IBKR: Connected   │
├──────────────────────────────────────────────────────────────┤
│ Net Liq       Gross Exposure    Leverage    Cash    Cushion  │
│ $____         $____             __x         $___    __%      │
├──────────────────────────────────────────────────────────────┤
│ Allocation                                                    │
│ US Equity          __%                                          │
│ International Eq.  __%                                          │
│ Bonds / Cash       __%                                          │
│ Commodities        __%                                          │
│ Alternatives       __%                                          │
├──────────────────────────────────────────────────────────────┤
│ Key Warnings                                                   │
│ - Margin cushion below threshold / OK                         │
│ - ETF holdings freshness: mixed / fresh / stale                │
│ - Top lookthrough exposure: ____                               │
└──────────────────────────────────────────────────────────────┘

Required fields from IBKR

Net liquidation value
Gross position value
Total cash value
Buying power
Initial margin requirement
Maintenance margin requirement
Excess liquidity
Cushion
SMA
Leverage

Functional requirements

Connect to TWS / IB Gateway
Show connection status
Show latest account summary
Show portfolio-level allocation
Show freshness timestamp
Show warnings

11.2 Positions

Purpose

Show raw IBKR positions.

User questions answered

What positions do I currently hold?
What is each position worth?
What is each position’s portfolio weight?
Can I open ETF research from a position?

Required UI

┌────────┬────────────────────────┬──────┬──────────┬──────────┬────────┐
│ Symbol │ Name                   │ Qty  │ Mkt Value│ Weight   │ P&L    │
├────────┼────────────────────────┼──────┼──────────┼──────────┼────────┤
│ VTI    │ Vanguard Total Market  │ 4    │ $___     │ 28.0%    │ +$__   │
│ SGOV   │ 0-3M Treasury ETF      │ 6    │ $___     │ 15.0%    │ +$__   │
│ QQQM   │ Nasdaq 100 ETF         │ 2    │ $___     │ 10.0%    │ +$__   │
└────────┴────────────────────────┴──────┴──────────┴──────────┴────────┘

Required columns

Symbol
Name
Asset type
Quantity
Average cost
Market price
Market value
Unrealized P&L
Portfolio weight
Currency
Account

Functional requirements

Load positions from IBKR
Calculate portfolio weights
Sort by market value
Sort by weight
Search by symbol
Open ETF research page for ETF positions
Show non-ETF positions clearly
Export positions

11.3 ETF Lookthrough

Purpose

Show effective underlying exposure across ETF holdings.

User questions answered

What do my ETFs make me own?
What is my effective exposure to Apple, Nvidia, Treasuries, gold, commodities, etc.?
How much hidden overlap exists?

Required formula

Effective holding exposure = Portfolio ETF weight × ETF holding weight

Example:

If VTI is 28% of portfolio
and AAPL is 6% of VTI
then effective AAPL exposure = 1.68% of portfolio

Required UI

┌──────────────────────────────────────────────────────────────┐
│ ETF Lookthrough                                               │
├────────┬────────────────────────┬────────────┬───────────────┤
│ Asset  │ Name                   │ Direct Wt  │ Effective Wt  │
├────────┼────────────────────────┼────────────┼───────────────┤
│ AAPL   │ Apple Inc.             │ 0.00%      │ 1.68%         │
│ MSFT   │ Microsoft Corp.        │ 0.00%      │ 1.54%         │
│ NVDA   │ NVIDIA Corp.           │ 0.00%      │ 1.32%         │
│ SGOV   │ Treasury Bills         │ 15.00%     │ 15.00%        │
└────────┴────────────────────────┴────────────┴───────────────┘

Required columns

Underlying ticker / identifier
Underlying name
Direct portfolio weight
Effective ETF-derived weight
Total effective weight
Source ETFs
Asset type
Sector
Country
Currency

Functional requirements

Map portfolio ETF positions to ETF holdings
Calculate effective lookthrough weights
Aggregate duplicate underlying holdings across ETFs
Show source ETF breakdown
Handle missing holdings data
Show data freshness
Export lookthrough table

Missing data handling

If an ETF has no holdings data:

Show ETF as unresolved exposure
Exclude from lookthrough aggregation
Display unresolved weight clearly

Example:

Unresolved ETF exposure: DBMF 10.0% — holdings unavailable or not parsed

11.4 Portfolio Exposure

Purpose

Aggregate exposures across the full portfolio.

User questions answered

What is my actual asset class exposure?
How much US equity do I have?
How much duration, commodity, international, small value, or cash exposure?

Required exposure categories

Asset class
Region
Country
Sector
Industry
Currency
Factor/style
Duration bucket
Credit quality
Commodity exposure
Issuer/fund family

Required UI

Portfolio Exposure
├── US Equity:              __%
├── International Equity:   __%
├── Treasury / Cash:        __%
├── Commodities:            __%
├── Trend / Alternatives:   __%
├── Gold:                   __%
└── Unclassified:           __%

Functional requirements

Aggregate direct holdings and ETF lookthrough holdings
Show exposure weights
Allow drilldown to source ETFs/positions
Show unclassified bucket
Export exposure

11.5 Portfolio Concentration

Purpose

Show concentration at the portfolio level.

User questions answered

Am I diversified?
Are my ETFs overlapping?
What are my largest effective holdings?
What are my largest sector/country/fund-family concentrations?

Required metrics

Top ETF positions
Top underlying effective holdings
Top sectors
Top countries
Top issuers
Top fund families
Top 10 effective holdings weight
Effective number of holdings
HHI concentration score
ETF overlap score

Required UI

Portfolio Concentration
├── Largest ETF position: VTI __%
├── Top 5 ETF positions: __%
├── Top 10 effective holdings: __%
├── Largest underlying exposure: ____ __%
├── Effective holdings: ____
├── ETF overlap: Low / Medium / High
└── Concentration verdict: Diversified / Moderate / Concentrated

Functional requirements

Calculate position-level concentration
Calculate lookthrough concentration
Calculate ETF overlap
Show top overlapping holdings
Show concentration warnings
Export concentration report

11.6 Margin

Purpose

Show IBKR margin and leverage status.

User questions answered

How levered am I?
What is my margin cushion?
How much buying power do I have?
How vulnerable is my account to a drawdown?

Required UI

┌──────────────────────────────────────────────────────────────┐
│ Margin Dashboard                                             │
├──────────────────────┬───────────────────────────────────────┤
│ Net Liq              │ $____                                 │
│ Gross Position Value │ $____                                 │
│ Leverage             │ __x                                   │
│ Buying Power         │ $____                                 │
│ Initial Margin Req   │ $____                                 │
│ Maintenance Margin   │ $____                                 │
│ Excess Liquidity     │ $____                                 │
│ Cushion              │ __%                                   │
│ SMA                  │ $____                                 │
├──────────────────────┴───────────────────────────────────────┤
│ Stress View                                                   │
│ -10% portfolio shock → Estimated Cushion: __%                 │
│ -20% portfolio shock → Estimated Cushion: __%                 │
└──────────────────────────────────────────────────────────────┘

Required IBKR fields

NetLiquidation
GrossPositionValue
BuyingPower
InitMarginReq
MaintMarginReq
ExcessLiquidity
Cushion
SMA
Leverage
TotalCashValue
AvailableFunds

Functional requirements

Display current margin values
Display leverage
Display cushion
Display cash and buying power
Display timestamp
Flag low cushion
Support simple shock scenarios

Required warnings

Cushion below warning threshold
Leverage above configured threshold
Negative cash balance
Large gross exposure relative to net liquidation
Unavailable or stale IBKR data

11.7 Portfolio Risk

Purpose

Summarize portfolio risk using IBKR account data and ETF exposure data.

User questions answered

What are my main risks?
Is my risk coming from leverage, equity beta, concentration, duration, commodities, or stale data?

Required risk categories

Leverage risk
Margin risk
Equity exposure risk
Duration risk
Commodity risk
Currency risk
Concentration risk
ETF overlap risk
Liquidity risk
Data freshness risk

Required UI

Portfolio Risk Summary
├── Leverage Risk: Medium
├── Margin Risk: Low / Medium / High
├── Equity Exposure: __%
├── Duration Exposure: __%
├── Commodity Exposure: __%
├── Top 10 Lookthrough Concentration: __%
├── ETF Overlap: Medium
└── Data Freshness: Mixed

Functional requirements

Show risk summary
Show risk labels
Show risk drivers
Show source data status
Support drilldown into each risk
Export risk report

12. Workspace Requirements

12.1 Watchlists

Purpose

Allow user to track ETFs without owning them.

Required watchlist types

My ETFs
Candidates
Reviewed
Compare Later

Functional requirements

Add ETF to watchlist
Remove ETF from watchlist
Open ETF from watchlist
Show whether ETF is owned in IBKR
Show latest data freshness

12.2 Notes

Purpose

Allow user research notes per ETF or portfolio.

Required note types

ETF note
Portfolio note
Risk note
Comparison note

Functional requirements

Create note
Edit note
Save note locally
Attach note to ETF
Attach note to portfolio view
Export notes

12.3 Exports

Purpose

Allow user to export research and analytics.

Required export formats

CSV
JSON
Markdown

Required export objects

ETF holdings
ETF exposure
ETF concentration
ETF comparison
Portfolio positions
ETF lookthrough
Portfolio exposure
Margin summary
Risk summary

12.4 Settings

Purpose

Configure data sources and app behavior.

Required settings

IBKR host
IBKR port
IBKR client ID
IBKR account selector
EDGAR identity / user agent
Cache directory
Data freshness thresholds
Margin warning threshold
Leverage warning threshold
Default export directory
Theme

13. Data Freshness Requirements

The app must show data freshness clearly.

Required freshness indicators

IBKR account data timestamp
IBKR positions timestamp
ETF holdings as-of date
ETF holdings filed date
Prospectus filed date
Fee data source date
Risk disclosure source date
Cache timestamp

Freshness states

Fresh
Acceptable
Stale
Unknown
Unavailable

Example

Holdings as of: 2026-03-31
Filed: 2026-04-28
Cached: 2026-05-19 16:21
Freshness: Acceptable

14. Provenance Requirements

Every derived data point must preserve its source.

Examples:

AAPL weight in VTI
Source: N-PORT / issuer holdings / cached date
Expense ratio
Source: Prospectus / N-1A / 497
Portfolio weight
Source: IBKR position data
Margin cushion
Source: IBKR account summary
Effective AAPL exposure
Source: IBKR portfolio weight × ETF holdings weight

15. Analytics Requirements

15.1 ETF-Level Analytics

Required calculations:

Top N holdings weight
Effective number of holdings
HHI concentration
Sector exposure
Country exposure
Asset class exposure
Issuer exposure
Fee summary
Risk category summary

15.2 Portfolio-Level Analytics

Required calculations:

Position weights
ETF lookthrough exposure
Direct + indirect exposure
Top underlying exposures
Portfolio sector exposure
Portfolio country exposure
Portfolio asset class exposure
Top 10 effective holdings weight
Portfolio HHI
ETF overlap
Leverage
Margin cushion
Simple shock cushion estimate

15.3 ETF Lookthrough Formula

effective_weight_underlying_i =
    sum(portfolio_weight_etf_j × holding_weight_i_in_etf_j)

15.4 Total Effective Exposure

total_effective_weight_i =
    direct_position_weight_i + ETF_lookthrough_weight_i

16. Error and Empty-State Requirements

16.1 IBKR disconnected

IBKR is disconnected.
Portfolio analytics are unavailable.
Research mode remains available.

Required actions:

Retry connection
Open settings
Continue in research-only mode

16.2 EDGAR unavailable

EDGAR data is unavailable.
Cached ETF data may still be used.

Required actions:

Use cache
Retry
Show source error

16.3 Holdings unavailable

Holdings are unavailable for this ETF.
The ETF will be shown as unresolved in portfolio lookthrough.

16.4 Partial lookthrough

Lookthrough coverage: 82%
Unresolved exposure: 18%

The app must not hide unresolved exposure.

17. MVP Scope

MVP must include

ETF Search
ETF Overview
ETF Holdings
ETF Exposure
ETF Concentration
ETF Fees
ETF Risk
ETF Documents
ETF Compare
IBKR Connection Status
Portfolio Overview
Positions
ETF Lookthrough
Portfolio Exposure
Portfolio Concentration
Margin
Portfolio Risk
Watchlists
Notes
Exports
Settings

MVP must exclude

Trade execution
Order preview
Portfolio income
Rebalance
Activity log
Tax reporting
Options analytics
Intraday strategy tools
Automated recommendations
LLM-generated trade ideas

18. Acceptance Criteria

18.1 ETF Search

Given a user searches for VTI
When matching ETF data exists
Then the app shows VTI in search results
And the user can open the ETF Overview

18.2 ETF Overview

Given a user opens an ETF
When overview data exists
Then the app shows ticker, fund name, issuer, asset class, source freshness, and portfolio ownership status

18.3 Holdings

Given ETF holdings are available
When the user opens Holdings
Then the app shows a sortable holdings table
And displays holdings as-of date and source

18.4 Exposure

Given ETF holdings are available
When the user opens Exposure
Then the app aggregates holdings into exposure categories
And shows unclassified exposure separately

18.5 Concentration

Given ETF holdings are available
When the user opens Concentration
Then the app shows top holdings concentration, effective holdings, and HHI score

18.6 Documents

Given EDGAR documents are available
When the user opens Documents
Then the app lists source documents by user-friendly document type
And also shows SEC form type and filing date

18.7 IBKR Connection

Given TWS or IB Gateway is running
When the user connects using configured host, port, and client ID
Then the app shows IBKR connected status
And account summary fields are displayed

18.8 Positions

Given IBKR positions are available
When the user opens Positions
Then the app shows symbol, quantity, market value, average cost, and portfolio weight

18.9 ETF Lookthrough

Given the user owns ETFs with available holdings data
When the user opens ETF Lookthrough
Then the app calculates effective underlying exposure
And shows unresolved ETF exposure separately

18.10 Margin

Given IBKR account summary is available
When the user opens Margin
Then the app shows net liquidation, gross position value, leverage, buying power, margin requirements, excess liquidity, cushion, and SMA

18.11 Portfolio Risk

Given portfolio and exposure data are available
When the user opens Portfolio Risk
Then the app shows leverage risk, margin risk, concentration risk, exposure risk, and data freshness risk

19. Suggested v1 User Flow

1. User opens app
2. App connects to IBKR if configured
3. User lands on Portfolio Overview
4. User checks net liquidation, leverage, cushion, and top exposure
5. User opens Positions
6. User selects VTI
7. App opens ETF Overview for VTI
8. User opens Holdings and Exposure
9. User returns to Portfolio Mode
10. User opens ETF Lookthrough
11. User reviews effective underlying holdings
12. User opens Margin
13. User exports portfolio risk summary to Markdown

20. UX Tone

The app should feel:

Fast
Keyboard-first
Analytical
Trustworthy
Minimal
Audit-friendly
Power-user oriented

The app should not feel:

Like a broker clone
Like a trade execution platform
Like a generic dashboard
Like a raw SEC filing browser
Like an AI black box

21. Final Product Shape

The final product should be organized around two core workspaces:

Research Mode
→ Understand ETFs
Portfolio Mode
→ Understand your actual IBKR ETF portfolio

The strongest feature is:

ETF lookthrough + IBKR margin-aware portfolio analytics

That is the product’s core differentiation.