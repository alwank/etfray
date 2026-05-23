"""Portfolio-level analytics - lookthrough, exposure, concentration."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class LookthroughHolding:
    ticker: str
    name: str
    direct_weight: float
    effective_weight: float
    total_weight: float
    source_etfs: list[str]
    asset_type: str = ""
    country: str = ""
    sector: str = ""


@dataclass
class UnresolvedETF:
    ticker: str
    portfolio_weight: float
    reason: str = "Holdings unavailable"


def calculate_lookthrough(
    positions: list[dict],  # [{symbol, weight}]
    holdings_cache: dict[str, pd.DataFrame],  # ticker -> holdings df
) -> tuple[list[LookthroughHolding], list[UnresolvedETF]]:
    """
    Calculate effective underlying exposure across ETF positions.
    effective_weight = portfolio_weight_etf × holding_weight_in_etf
    """
    aggregated: dict[str, LookthroughHolding] = {}
    unresolved: list[UnresolvedETF] = []

    for pos in positions:
        symbol = pos["symbol"]
        port_weight = pos["weight"]

        if symbol not in holdings_cache or holdings_cache[symbol] is None or holdings_cache[symbol].empty:
            unresolved.append(UnresolvedETF(ticker=symbol, portfolio_weight=port_weight))
            continue

        df = holdings_cache[symbol]
        value_col = "pct_value" if "pct_value" in df.columns else "value_usd"
        total = float(df[value_col].abs().sum())
        if total == 0:
            unresolved.append(UnresolvedETF(ticker=symbol, portfolio_weight=port_weight))
            continue

        for _, row in df.iterrows():
            if str(row.get("asset_category", "") or "").strip().upper() == "STIV":
                continue
            raw_ticker = row.get("ticker", "")
            hticker = "" if pd.isna(raw_ticker) else str(raw_ticker).strip().upper()
            if hticker == symbol:
                continue
            hname = str(row.get("name", "") or "")
            h_weight = (abs(float(row[value_col])) / total * 100) if value_col == "value_usd" else abs(float(row[value_col]))
            effective = port_weight * h_weight / 100

            key = hticker if hticker else hname
            if key in aggregated:
                aggregated[key].effective_weight += effective
                aggregated[key].total_weight += effective
                if symbol not in aggregated[key].source_etfs:
                    aggregated[key].source_etfs.append(symbol)
            else:
                aggregated[key] = LookthroughHolding(
                    ticker=hticker,
                    name=hname,
                    direct_weight=0.0,
                    effective_weight=effective,
                    total_weight=effective,
                    source_etfs=[symbol],
                    asset_type=str(row.get("asset_category", "") or ""),
                    country=str(row.get("investment_country", "") or ""),
                )

    # Sort by total weight descending
    sorted_holdings = sorted(aggregated.values(), key=lambda x: x.total_weight, reverse=True)
    return sorted_holdings, unresolved


def calculate_portfolio_exposure(
    lookthrough: list[LookthroughHolding],
    group_by: str = "country",
) -> list[tuple[str, float]]:
    """Aggregate lookthrough holdings into exposure categories."""
    buckets: dict[str, float] = {}
    for h in lookthrough:
        key = getattr(h, group_by, "") or "Unclassified"
        buckets[key] = buckets.get(key, 0) + h.total_weight

    return sorted(buckets.items(), key=lambda x: x[1], reverse=True)
