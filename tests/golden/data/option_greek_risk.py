"""Generate synthetic data for option_greek_risk golden test."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd


def generate() -> None:
    """Generate option and underlying price data."""
    data_dir = Path(__file__).parent
    dates = pd.date_range("2024-01-02", periods=10, freq="B")

    # Option: ATM call, price ~5.0
    df_opt = pd.DataFrame(
        {
            "timestamp": dates,
            "open": 5.0,
            "high": 5.5,
            "low": 4.5,
            "close": 5.0,
            "volume": 1000,
            "symbol": "CALL_OPT",
        }
    )

    # Underlying: price ~100 (strike=100, ATM)
    df_ul = pd.DataFrame(
        {
            "timestamp": dates,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 10000,
            "symbol": "UL",
        }
    )

    combined = pd.concat([df_opt, df_ul], ignore_index=True)
    combined.to_parquet(data_dir / "option_greek_risk.parquet", index=False)
    print(f"Generated {len(combined)} rows -> option_greek_risk.parquet")


if __name__ == "__main__":
    generate()
