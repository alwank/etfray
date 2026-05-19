"""CSV export service for ETF Terminal."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def export_dataframe_csv(df: pd.DataFrame, name: str, export_dir: str) -> str:
    """Export a DataFrame to CSV. Returns the file path."""
    out_dir = Path(export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{name}_{date.today().isoformat()}.csv"
    path = out_dir / filename
    df.to_csv(path, index=False)
    return str(path)
