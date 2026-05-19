"""ETF analytics - exposure, concentration, and risk calculations."""

from __future__ import annotations
import pandas as pd
from dataclasses import dataclass


# SEC asset category codes to readable names
ASSET_CATEGORY_MAP = {
    "EC": "Equity - Common",
    "EP": "Equity - Preferred",
    "DBT": "Debt",
    "STIV": "Short-Term Investment",
    "ABS": "Asset-Backed Security",
    "MBS": "Mortgage-Backed Security",
    "USG": "US Government",
    "MUN": "Municipal",
    "CORP": "Corporate",
    "OTH": "Other",
    "": "Unclassified",
}


@dataclass
class ExposureBreakdown:
    category: str
    weight: float
    count: int


@dataclass
class ConcentrationMetrics:
    num_holdings: int
    top1_weight: float
    top5_weight: float
    top10_weight: float
    top25_weight: float
    top50_weight: float
    largest_holding: str
    hhi: float
    effective_n: float
    verdict: str


def calculate_exposure(df: pd.DataFrame, group_col: str) -> list[ExposureBreakdown]:
    """Aggregate holdings into exposure categories by a given column."""
    if df.empty or group_col not in df.columns:
        return []

    value_col = "pct_value" if "pct_value" in df.columns else "value_usd"
    total = float(df[value_col].sum())
    if total == 0:
        return []

    grouped = df.groupby(group_col).agg(
        weight=(value_col, "sum"),
        count=(value_col, "count"),
    ).sort_values("weight", ascending=False)

    results = []
    for cat, row in grouped.iterrows():
        label = str(cat) if cat else "Unclassified"
        if group_col == "asset_category":
            label = ASSET_CATEGORY_MAP.get(str(cat), str(cat))
        pct = (float(row["weight"]) / total * 100) if value_col == "value_usd" else float(row["weight"])
        results.append(ExposureBreakdown(category=label, weight=round(pct, 2), count=int(row["count"])))

    return results


def calculate_concentration(df: pd.DataFrame) -> ConcentrationMetrics:
    """Calculate concentration metrics from holdings DataFrame."""
    if df.empty:
        return ConcentrationMetrics(0, 0, 0, 0, 0, 0, "", 0, 0, "No data")

    value_col = "pct_value" if "pct_value" in df.columns else "value_usd"
    sorted_df = df.sort_values(value_col, ascending=False)

    total = float(sorted_df[value_col].sum())
    if total == 0:
        return ConcentrationMetrics(0, 0, 0, 0, 0, 0, "", 0, 0, "No data")

    # Normalize weights
    import numpy as np
    weights = (sorted_df[value_col].astype(float) / total * 100).values

    n = len(weights)
    top1 = float(weights[0]) if n >= 1 else 0
    top5 = float(sum(weights[:5])) if n >= 5 else float(sum(weights))
    top10 = float(sum(weights[:10])) if n >= 10 else float(sum(weights))
    top25 = float(sum(weights[:25])) if n >= 25 else float(sum(weights))
    top50 = float(sum(weights[:50])) if n >= 50 else float(sum(weights))

    # HHI = sum of squared weights (as fractions)
    w_frac = weights / 100
    hhi = float(sum(w_frac ** 2))
    effective_n = 1 / hhi if hhi > 0 else n

    # Largest holding name
    largest = str(sorted_df.iloc[0].get("name", "") or sorted_df.iloc[0].get("ticker", ""))

    # Verdict
    if effective_n > 100:
        verdict = "Broadly diversified"
    elif effective_n > 30:
        verdict = "Moderately concentrated"
    else:
        verdict = "Highly concentrated"

    return ConcentrationMetrics(
        num_holdings=n,
        top1_weight=round(top1, 2),
        top5_weight=round(top5, 2),
        top10_weight=round(top10, 2),
        top25_weight=round(top25, 2),
        top50_weight=round(top50, 2),
        largest_holding=largest[:30],
        hhi=round(hhi, 6),
        effective_n=round(effective_n, 1),
        verdict=verdict,
    )
