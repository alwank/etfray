"""IBKR data service wrapping ib_async for portfolio data."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """Service for connecting to IBKR TWS/Gateway via ib_async."""

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
        """Connect to TWS/Gateway. Returns True on success."""
        try:
            from ib_async import IB
            self._ib = IB()
            self._ib.connect(host, port, clientId=client_id)
            self._connected = True
            self._refresh_data()
            return True
        except Exception:
            self._connected = False
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

        # Account summary
        try:
            accounts = self._ib.managedAccounts()
            account = accounts[0] if accounts else ""
            summary_items = self._ib.accountSummary(account)

            s = AccountSummary(timestamp=datetime.now().isoformat())
            for item in summary_items:
                tag = item.tag
                val = float(item.value) if item.value else 0.0
                if tag == "NetLiquidation":
                    s.net_liquidation = val
                elif tag == "GrossPositionValue":
                    s.gross_position_value = val
                elif tag == "TotalCashValue":
                    s.total_cash_value = val
                elif tag == "BuyingPower":
                    s.buying_power = val
                elif tag == "InitMarginReq":
                    s.init_margin_req = val
                elif tag == "MaintMarginReq":
                    s.maint_margin_req = val
                elif tag == "ExcessLiquidity":
                    s.excess_liquidity = val
                elif tag == "Cushion":
                    s.cushion = val
                elif tag == "SMA":
                    s.sma = val
                elif tag == "Leverage":
                    s.leverage = val
                elif tag == "AvailableFunds":
                    s.available_funds = val
            self._account_summary = s
        except Exception:
            pass

        # Positions
        try:
            raw_positions = self._ib.positions()
            self._positions = []
            for p in raw_positions:
                contract = p.contract
                pos = Position(
                    symbol=contract.symbol,
                    name=getattr(contract, "localSymbol", contract.symbol),
                    asset_type=contract.secType,
                    quantity=p.position,
                    avg_cost=p.avgCost,
                    market_value=p.position * p.avgCost,  # approximate
                    currency=contract.currency,
                    account=p.account,
                )
                self._positions.append(pos)
        except Exception:
            pass


# Singleton instance
_service: IBKRService | None = None


def get_ibkr_service() -> IBKRService:
    global _service
    if _service is None:
        _service = IBKRService()
    return _service
