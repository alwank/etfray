# Tutorial: Portfolio Setup

This tutorial shows how to connect etfray to your IBKR account for portfolio analytics.

## Prerequisites

- IBKR TWS or IB Gateway installed and running
- API connections enabled (see [IBKR Setup](../user-guide/ibkr-setup.md))
- At least one open ETF position in your account

## Steps

### 1. Configure connection

Open Settings (Workspace → Settings in the sidebar) and verify:

- Host: `127.0.0.1`
- Port: `7497` (TWS) or `4001` (Gateway)
- Client ID: `1`

### 2. Start etfray with TWS/Gateway running

Launch the app (`etfray`). The splash screen attempts to connect to IBKR using your Settings. When connection succeeds, the status bar shows **IBKR: Connected**.

### 3. Open Portfolio Overview

Use the sidebar to expand **Portfolio** and select **Overview**. Your account summary should already be loaded if the splash connection succeeded. If not, click **Connect IBKR** or press `Ctrl+I`.

### 4. View positions

Switch to **Positions** to see all holdings with market value and portfolio weight.

### 5. Lookthrough analysis

The **Lookthrough** view decomposes your ETF positions into underlying holdings. If you hold VTI and QQQM, you'll see the combined underlying stocks weighted by your position sizes.

### 6. Check concentration

**Concentration** shows your true single-stock exposure across all ETFs. You might discover you have 8% in Apple across multiple funds.

### 7. Monitor margin

The **Margin** view shows leverage ratio, maintenance margin, and available buying power. Warnings appear when leverage exceeds your configured threshold.
