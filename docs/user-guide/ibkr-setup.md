# IBKR Setup

etfray connects to Interactive Brokers TWS or IB Gateway via the TWS API to retrieve live portfolio data.

## Prerequisites

Install one of:

- [IBKR Trader Workstation (TWS)](https://www.interactivebrokers.com/en/trading/tws.php)
- [IB Gateway](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) (lighter, headless)

## Enable API Connections

1. Open TWS or IB Gateway
2. Go to **Edit → Global Configuration → API → Settings**
3. Check **Enable ActiveX and Socket Clients**
4. Set **Socket port** to `7497` (TWS paper) or `4001` (Gateway)
5. Uncheck **Read-Only API** if you want full access (etfray only reads data)

## Configure etfray

Open Settings in etfray (`ctrl+,`) and set:

- **Host**: `127.0.0.1` (default)
- **Port**: `7497` (TWS) or `4001` (Gateway)
- **Client ID**: `1` (any unused integer)

## Connection

Navigate to any Portfolio view — etfray will automatically connect when portfolio data is needed.

!!! note
    etfray is read-only. It never places trades or modifies your account.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | Ensure TWS/Gateway is running and API is enabled |
| Port mismatch | Check the socket port in TWS API settings matches etfray config |
| Client ID conflict | Use a different client ID if another app is connected |
| No positions shown | Ensure you have open positions and the account has market data subscriptions |
