# Tutorial: Evaluating a 3-Fund Portfolio

This tutorial walks through using etfray's Portfolio Analytics to analyze a classic three-fund portfolio and uncover hidden concentration, sector tilts, and geographic exposure.

## The Scenario

You hold a common three-fund portfolio:

- **VTI** (US Total Stock Market) — 60% of portfolio
- **VXUS** (International Stock Market) — 30% of portfolio
- **BND** (US Aggregate Bond) — 10% of portfolio

This is widely considered a well-diversified allocation. But what does it actually look like at the stock level?

## Prerequisites

- IBKR TWS/Gateway running with these positions (or similar)
- etfray connected (see [IBKR Setup](../user-guide/ibkr-setup.md))

## Steps

### 1. Check your positions

Navigate to **Portfolio → Positions**. Confirm your holdings and their portfolio weights. The weights should roughly match your target allocation.

### 2. View lookthrough exposure

Switch to **Portfolio → Lookthrough**. etfray decomposes each ETF into its underlying holdings and weights them by your position size.

**What you'll see:**

Your top underlying holdings will be something like:

| Stock | Effective Weight | Source ETFs |
|-------|-----------------|-------------|
| Apple | ~3.9% | VTI |
| Microsoft | ~3.6% | VTI |
| Nvidia | ~3.0% | VTI |
| Amazon | ~2.1% | VTI |
| Taiwan Semiconductor | ~1.2% | VXUS |

Notice that your top single-stock exposures all come from VTI. Even in a "diversified" portfolio, the US mega-caps dominate because VTI is cap-weighted and makes up 60% of your portfolio.

!!! note
    BND (bonds) will likely appear in the "unresolved" list since its holdings are individual bonds, not stocks. This is expected — bond ETF lookthrough is less meaningful at the individual security level.

### 3. Check sector exposure

Switch to **Portfolio → Exposure**. This aggregates sector exposure across all your equity ETFs.

**Typical result for this portfolio:**

| Sector | Weight |
|--------|--------|
| Technology | ~22% |
| Financials | ~14% |
| Healthcare | ~12% |
| Consumer Discretionary | ~10% |
| Industrials | ~10% |

The sector weights are dominated by VTI (60% of portfolio) with VXUS (30%) adding some international sector diversification. Technology is your largest sector bet — driven by US mega-cap tech.

### 4. Check geographic exposure

Still in the Exposure view, look at geographic breakdown:

| Region | Weight |
|--------|--------|
| United States | ~60% |
| Japan | ~5% |
| United Kingdom | ~3% |
| China | ~3% |
| Other international | ~19% |
| Bonds (unresolved) | ~10% |

Your equity allocation is roughly 67% US / 33% international (excluding bonds), which matches the VTI/VXUS ratio.

### 5. Analyze concentration

Switch to **Portfolio → Concentration**. This shows your effective diversification at the stock level.

**Key metrics to look for:**

- **Top 10 weight:** ~25% — your top 10 stocks make up a quarter of your equity exposure
- **Effective N:** ~80–100 — despite holding thousands of underlying stocks, your portfolio behaves like ~80–100 equal-weight positions
- **Verdict:** "Broadly diversified" — but less so than you might expect from holding 7,000+ underlying stocks

### 6. Insights and actions

**What this analysis reveals:**

1. **Hidden concentration in US mega-caps** — Apple alone is ~4% of your portfolio. The top 5 US tech stocks are ~15% combined.
2. **Sector tilt toward technology** — Not a problem if intentional, but worth knowing.
3. **Geographic diversification is working** — VXUS provides genuine international exposure with minimal overlap to VTI.
4. **Bonds are opaque** — BND's individual bond holdings don't decompose well, but that's fine — the 10% allocation provides its diversification benefit at the asset-class level.

**Possible adjustments (not recommendations, just observations):**

- If 4% in Apple concerns you, consider equal-weight alternatives (like RSP instead of VOO)
- If you want less tech concentration, VXUS naturally has lower tech weight than VTI
- The 60/30/10 split is already well-diversified — the "hidden concentration" is inherent to cap-weighting, not a portfolio construction flaw

## Next Steps

- Run the [Overlap Analysis](overlap-analysis.md) between VTI and VXUS to confirm they're complementary (~0% overlap expected)
- Check the [Margin Monitoring](margin-monitoring.md) tutorial if you use leverage
- Export your lookthrough data (`ctrl+s`) for further analysis in a spreadsheet
