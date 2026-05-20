"""IBKR data service wrapping ib_async for portfolio data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AccountSummary:
    net_liquidation: float = 0.0
    gross_position_value: float = 0.0
    total_cash_value: float = 0.0
    buying_power: float = 0.0
    init_margin_req: float = 0.0
    maint_margin_req: float = 0.0
    excess_liquidity: float = 0.0
    cushion: float = 0.0
    sma: float = 0.0
    leverage: float = 0.0
    available_funds: float = 0.0
    timestamp: str = ""


@dataclass
class Position:
    symbol: str
    name: str = ""
    asset_type: str = "STK"
    quantity: float = 0.0
    avg_cost: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    currency: str = "USD"
    account: str = ""


class IBKRService:
    """Service for connecting to IBKR TWS/Gateway via ib_async.

    READ-ONLY: This service only fetches account data and positions.
    No order placement or account modifications are permitted.
    """

    def __init__(self):
        self._ib = None
        self._connected = False
        self._account_summary: AccountSummary | None = None
        self._positions: list[Position] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def account_summary(self) -> AccountSummary | None:
        return self._account_summary

    @property
    def positions(self) -> list[Position]:
        return self._positions

    def connect(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1) -> bool:
        """Connect to TWS/Gateway (read-only). Returns True on success."""
        self.disconnect()  # Clean up any stale connection
        try:
            from ib_async import IB
            self._ib = IB()
            self._ib.connect(host, port, clientId=client_id, readonly=True, timeout=4)
            self._connected = True
            self._refresh_data()
            return True
        except Exception as e:
            self._connected = False
            self._last_error = f"{type(e).__name__}: {e}"
            self._ib = None
            return False

    def disconnect(self) -> None:
        if self._ib:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._connected = False
        self._ib = None

    def refresh(self) -> None:
        """Refresh account data and positions."""
        if self._connected and self._ib:
            self._refresh_data()

    def _refresh_data(self) -> None:
        if not self._ib:
            return

        self._ib.sleep(2)

        # Account summary from accountValues
        try:
            s = AccountSummary(timestamp=datetime.now().isoformat())
            for av in self._ib.accountValues():
                if av.currency not in ("USD", ""):
                    continue
                tag, val = av.tag, av.value
                try:
                    v = float(val)
                except (ValueError, TypeError):
                    continue
                if tag == "NetLiquidation":
                    s.net_liquidation = v
                elif tag == "GrossPositionValue":
                    s.gross_position_value = v
                elif tag == "TotalCashValue":
                    s.total_cash_value = v
                elif tag == "BuyingPower":
                    s.buying_power = v
                elif tag == "InitMarginReq":
                    s.init_margin_req = v
                elif tag == "MaintMarginReq":
                    s.maint_margin_req = v
                elif tag == "ExcessLiquidity":
                    s.excess_liquidity = v
                elif tag == "Cushion":
                    s.cushion = v
                elif tag == "SMA":
                    s.sma = v
                elif tag == "Leverage-S":
                    s.leverage = v
                elif tag == "AvailableFunds":
                    s.available_funds = v
            self._account_summary = s
        except Exception:
            pass

        # Positions from portfolio() - includes market price and PnL
        try:
            self._positions = []
            for p in self._ib.portfolio():
                contract = p.contract
                self._positions.append(Position(
                    symbol=contract.symbol,
                    name=getattr(contract, "localSymbol", contract.symbol),
                    asset_type=contract.secType,
                    quantity=p.position,
                    avg_cost=p.averageCost,
                    market_price=p.marketPrice,
                    market_value=p.marketValue,
                    unrealized_pnl=p.unrealizedPNL,
                    currency=contract.currency,
                    account=p.account,
                ))
        except Exception:
            pass


# Singleton instance
_service: IBKRService | None = None


def get_ibkr_service() -> IBKRService:
    global _service
    if _service is None:
        _service = IBKRService()
    return _service
