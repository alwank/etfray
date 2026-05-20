# IBKR Setup

etfray connects to Interactive Brokers TWS or IB Gateway via the TWS API to retrieve live portfolio data.

## Prerequisites

Install one of:

- [IBKR Trader Workstation (TWS)](https://www.interactivebrokers.com/en/trading/tws.php) — Full trading platform with GUI
- [IB Gateway](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) — Lightweight, headless API server

### Which should I use?

| | TWS | IB Gateway |
|---|---|---|
| Best for | Interactive use alongside etfray | Always-on / headless setups |
| Resource usage | Higher (full GUI) | Lower (minimal UI) |
| Default port | 7497 (paper), 7496 (live) | 4002 (paper), 4001 (live) |
| Auto-restart | No | Yes (with IBC) |

**Recommendation:** Use IB Gateway if you want etfray to always have access to portfolio data without keeping TWS open. Use TWS if you also trade interactively.

## Enable API Connections

1. Open TWS or IB Gateway
2. Go to **Edit → Global Configuration → API → Settings**
3. Check **Enable ActiveX and Socket Clients**
4. Set **Socket port** to `7497` (TWS paper) or `4001` (Gateway live)
5. Uncheck **Read-Only API** if you want full access (etfray only reads data regardless)
6. Optionally add `127.0.0.1` to **Trusted IPs** to skip the connection confirmation dialog

## Configure etfray

Open Settings in etfray (Workspace → Settings in the sidebar) and set:

- **Host**: `127.0.0.1` (default — only change if TWS/Gateway runs on another machine)
- **Port**: `7497` (TWS paper), `7496` (TWS live), `4002` (Gateway paper), `4001` (Gateway live)
- **Client ID**: `1` (any unused integer — must be unique across all connected applications)

## Connection Behavior

etfray connects **lazily** — it only establishes the IBKR connection when you first navigate to a Portfolio view. This means:

- The app starts instantly without waiting for IBKR
- If TWS/Gateway isn't running, Research features work normally
- Connection errors only appear when you access Portfolio views

## Security

!!! info "Read-only by design"
    etfray connects with `readonly=True`. It **cannot** place orders, modify positions, or change account settings — even if "Read-Only API" is unchecked in TWS. The connection is strictly for reading account data and positions.

**Network security:**

- etfray only connects to `localhost` by default. No data leaves your machine via the IBKR connection.
- If you change `ibkr_host` to a remote address, ensure the connection is over a trusted network.
- The TWS API does not use encryption. Do not expose the API port to untrusted networks.

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Connection refused | TWS/Gateway not running or API disabled | Start TWS/Gateway and enable API in settings |
| Port mismatch | etfray port doesn't match TWS/Gateway | Check socket port in TWS API settings, update etfray config |
| Client ID conflict | Another app using the same client ID | Change `ibkr_client_id` to an unused number (e.g., 2, 3) |
| No positions shown | No open positions, or account lacks market data | Verify positions exist in TWS; check market data subscriptions |
| Stale data | Positions loaded but not updating | Navigate away from Portfolio and back, or restart etfray |
| Connection drops | TWS/Gateway restarted or network interruption | Navigate to any Portfolio view to trigger reconnection |
| "Timeout" error | TWS/Gateway is slow to respond | Increase timeout by restarting TWS/Gateway; ensure it's fully loaded before connecting |
| Multiple accounts | Wrong account's data showing | Ensure the correct account is selected in TWS/Gateway before connecting |

### Common mistakes

1. **Forgetting to enable the API** — The API is disabled by default in TWS. You must explicitly enable it in Global Configuration.
2. **Using the wrong port** — Paper and live accounts use different ports. Double-check which you're connecting to.
3. **Running TWS in "offline" mode** — If TWS can't connect to IBKR servers, market data and some account values won't be available.
4. **Firewall blocking localhost** — Rare, but some security software blocks local socket connections. Add an exception for the API port.

## Market Data Considerations

Position quantities and average cost are always available, but **market prices** require active market data subscriptions in your IBKR account. Without subscriptions:

- Market value may show as 0 or use the previous close
- Unrealized P&L may be inaccurate
- Portfolio weights will be incorrect

This is an IBKR limitation, not an etfray issue. Check your market data subscriptions in Account Management.
