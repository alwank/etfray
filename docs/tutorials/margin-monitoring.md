# Tutorial: Margin Monitoring

This tutorial shows how to configure and use etfray's margin monitoring to get early warnings before approaching maintenance margin limits.

## The Scenario

You use margin in your IBKR account — perhaps 1.3× leverage to boost returns. You want etfray to warn you before your cushion gets dangerously low, giving you time to reduce positions or add cash before a margin call.

## Prerequisites

- IBKR account with margin enabled
- TWS/Gateway running and connected to etfray
- At least one position using margin (gross position value > net liquidation)

## Key Concepts

Before diving in, here's what the margin metrics mean:

| Metric | Formula | Plain English |
|--------|---------|---------------|
| **Net liquidation** | Total account value if all positions closed | Your equity |
| **Gross position value** | Sum of absolute market values | Total exposure |
| **Leverage ratio** | Gross position / Net liquidation | How leveraged you are (1.0 = no margin) |
| **Maintenance margin** | IBKR's minimum equity requirement | The floor — go below this and you get a margin call |
| **Excess liquidity** | Net liquidation − Maintenance margin | Dollar buffer above the margin call line |
| **Cushion** | Excess liquidity / Net liquidation | Buffer as a percentage of equity |

**Example:** With $100K net liquidation, $130K gross positions, and $50K maintenance margin:

- Leverage: 1.3× ($130K / $100K)
- Excess liquidity: $50K ($100K − $50K)
- Cushion: 50% ($50K / $100K)

## Steps

### 1. Configure warning thresholds

Open Settings (Workspace → Settings in the sidebar) and set your preferred thresholds:

**Margin cushion warning** (`margin_warning_cushion`):

- Default: `0.15` (15%) — warns when your buffer is only 15% of equity
- Conservative: `0.25` (25%) — earlier warning, more time to react
- Aggressive: `0.10` (10%) — later warning, closer to the edge

**Leverage warning** (`leverage_warning`):

- Default: `2.0` — warns at 2× leverage
- Conservative: `1.5` — warns earlier
- Aggressive: `3.0` — only warns at extreme leverage

!!! tip
    Start conservative. You can always loosen thresholds later. A 25% cushion warning gives you meaningful time to act before a margin call becomes imminent.

### 2. Navigate to the Margin view

Go to **Portfolio → Margin**. etfray displays your current margin metrics:

- Net liquidation value
- Gross position value
- Leverage ratio
- Maintenance margin requirement
- Excess liquidity
- Cushion percentage
- Buying power remaining

### 3. Understand the warnings

Warnings appear when:

- **Cushion drops below threshold** — Your buffer is getting thin. A market drop could push you toward a margin call.
- **Leverage exceeds threshold** — You're more leveraged than your comfort level. This can happen passively if your positions appreciate while cash stays constant.

!!! warning
    etfray warnings are informational only. It does not auto-liquidate or place any trades. You must act in TWS/Gateway if you want to reduce exposure.

### 4. Interpret margin changes over time

Margin metrics change with the market:

| Market moves | Effect on leverage | Effect on cushion |
|---|---|---|
| Positions go up | Leverage increases slightly (positions grow, equity grows less) | Cushion may decrease |
| Positions go down | Leverage can spike (equity drops faster than positions) | Cushion drops — danger zone |
| You add cash | Leverage decreases | Cushion increases |
| You close positions | Leverage decreases | Cushion increases |

**The dangerous scenario:** A market drop reduces your equity (net liquidation) while maintenance margin stays roughly the same. This compresses your cushion rapidly. A 10% market drop can cut your cushion in half.

### 5. What to do when warnings fire

1. **Don't panic** — A warning means you're approaching a threshold, not that a margin call is imminent.
2. **Check the numbers** — Navigate to Margin view and assess how close you actually are.
3. **Consider your options:**
   - Close some positions to reduce leverage
   - Add cash to increase equity
   - Do nothing if you believe the market will recover (risky)
4. **Act in TWS/Gateway** — etfray is read-only. Place any trades through your normal trading interface.

## Example: Setting Up Conservative Monitoring

For a moderately leveraged portfolio (1.3×), a conservative setup would be:

```
margin_warning_cushion: 0.25
leverage_warning: 1.5
```

This means:

- You'll be warned when cushion drops below 25% (plenty of buffer before a real margin call)
- You'll be warned if leverage creeps above 1.5× (even though you're comfortable at 1.3×, this catches drift)

With $100K equity and 1.3× leverage:

- Maintenance margin ≈ $32K (25% of $130K gross)
- Excess liquidity = $100K − $32K = $68K
- Cushion = 68% — well above the 25% warning

A ~50% market drop would be needed to trigger the cushion warning. That's a comfortable buffer.

## Next Steps

- Combine margin monitoring with [concentration analysis](three-fund-analysis.md) — concentrated positions on margin are the highest-risk scenario
- Export margin data (click **Export** in the Margin view) to track your leverage over time
- See [Configuration](../user-guide/configuration.md#example-configurations) for more threshold examples
