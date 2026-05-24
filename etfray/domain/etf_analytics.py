"""ETF analytics - exposure, concentration, and risk calculations."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

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

    grouped = (
        df.groupby(group_col)
        .agg(
            weight=(value_col, "sum"),
            count=(value_col, "count"),
        )
        .sort_values("weight", ascending=False)
    )

    results = []
    for cat, row in grouped.iterrows():
        label = str(cat) if cat else "Unclassified"
        if group_col == "asset_category":
            label = ASSET_CATEGORY_MAP.get(str(cat), str(cat))
        raw = float(row["weight"])
        pct = raw if value_col == "pct_value" else raw / total * 100
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
    weights = (sorted_df[value_col].astype(float) / total * 100).values

    n = len(weights)
    top1 = float(weights[0]) if n >= 1 else 0
    top5 = float(sum(weights[:5])) if n >= 5 else float(sum(weights))
    top10 = float(sum(weights[:10])) if n >= 10 else float(sum(weights))
    top25 = float(sum(weights[:25])) if n >= 25 else float(sum(weights))
    top50 = float(sum(weights[:50])) if n >= 50 else float(sum(weights))

    # HHI = sum of squared weights (as fractions)
    w_frac = weights / 100
    hhi = float(sum(w_frac**2))
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


@dataclass
class GroupConcentration:
    group_col: str
    num_groups: int
    top1_name: str
    top1_weight: float
    top3_weight: float
    top5_weight: float
    hhi: float
    entries: list[tuple[str, float]]  # (name, weight%) top entries


def calculate_group_concentration(df: pd.DataFrame, group_col: str) -> GroupConcentration | None:
    """Calculate concentration metrics grouped by a column (country, asset_category)."""
    if df.empty or group_col not in df.columns:
        return None

    value_col = "pct_value" if "pct_value" in df.columns else "value_usd"
    total = float(df[value_col].sum())
    if total == 0:
        return None

    grouped = df.groupby(group_col)[value_col].sum().sort_values(ascending=False)
    if value_col == "value_usd":
        grouped = grouped / total * 100

    names = [str(n) if n else "Unclassified" for n in grouped.index]
    weights = grouped.values.astype(float)
    n = len(weights)

    top1_w = float(weights[0]) if n >= 1 else 0
    top3_w = float(weights[:3].sum()) if n >= 3 else float(weights.sum())
    top5_w = float(weights[:5].sum()) if n >= 5 else float(weights.sum())

    w_frac = weights / 100
    hhi = float((w_frac**2).sum())

    entries = [(names[i], round(float(weights[i]), 2)) for i in range(min(5, n))]

    return GroupConcentration(
        group_col=group_col,
        num_groups=n,
        top1_name=names[0] if names else "",
        top1_weight=round(top1_w, 2),
        top3_weight=round(top3_w, 2),
        top5_weight=round(top5_w, 2),
        hhi=round(hhi, 6),
        entries=entries,
    )


def calculate_weight_overlap(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
    """Calculate weight-adjusted overlap: sum(min(w_a, w_b)) for shared tickers.

    Returns overlap as a percentage (0-100).
    """
    if df_a.empty or df_b.empty:
        return 0.0

    if "ticker" not in df_a.columns or "ticker" not in df_b.columns:
        return 0.0

    value_col = "pct_value" if "pct_value" in df_a.columns else "value_usd"

    # Normalize weights to sum to 100
    a = df_a[["ticker", value_col]].copy()
    b = df_b[["ticker", value_col]].copy()
    a["ticker"] = a["ticker"].astype(str).str.upper().str.strip()
    b["ticker"] = b["ticker"].astype(str).str.upper().str.strip()
    a = a[a["ticker"] != ""]
    b = b[b["ticker"] != ""]

    total_a = a[value_col].sum()
    total_b = b[value_col].sum()
    if total_a == 0 or total_b == 0:
        return 0.0

    a["w"] = a[value_col] if value_col == "pct_value" else a[value_col] / total_a * 100
    b["w"] = b[value_col] if value_col == "pct_value" else b[value_col] / total_b * 100

    # Group by ticker (sum duplicates)
    a = a.groupby("ticker")["w"].sum()
    b = b.groupby("ticker")["w"].sum()

    shared = a.index.intersection(b.index)
    if shared.empty:
        return 0.0

    overlap = sum(min(a[t], b[t]) for t in shared)
    return round(float(overlap), 2)
