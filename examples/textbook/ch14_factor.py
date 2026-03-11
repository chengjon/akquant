import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from akquant.data import ParquetDataCatalog
from akquant.factor import FactorEngine


def _build_catalog(catalog_path: Path) -> ParquetDataCatalog:
    if catalog_path.exists():
        shutil.rmtree(catalog_path)
    catalog = ParquetDataCatalog(root_path=str(catalog_path))
    rng = np.random.default_rng(42)
    dates = pd.date_range("2023-01-01", periods=90, freq="D")
    symbols = [("AAA", 50.0, 0.12), ("BBB", 80.0, -0.05), ("CCC", 30.0, 0.2)]
    for symbol, base, drift in symbols:
        noise = rng.normal(0.0, 0.6, len(dates))
        close = base + drift * np.arange(len(dates)) + np.cumsum(noise) * 0.2
        open_ = close + rng.normal(0.0, 0.2, len(dates))
        high = np.maximum(open_, close) + np.abs(rng.normal(0.0, 0.3, len(dates)))
        low = np.minimum(open_, close) - np.abs(rng.normal(0.0, 0.3, len(dates)))
        volume = rng.integers(100_000, 600_000, len(dates))
        df = pd.DataFrame(
            {
                "date": dates,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "symbol": symbol,
            }
        ).set_index("date")
        catalog.write(symbol, df)
    return catalog


def _run_demo() -> None:
    catalog_path = Path("temp_textbook_ch14_catalog")
    try:
        catalog = _build_catalog(catalog_path)
        engine = FactorEngine(catalog)
        expressions = [
            "Ts_Mean(Close, 5)",
            "Ts_Std(Close, 20)",
            "Rank(Volume)",
            "Rank(Ts_Corr(Close, Volume, 10))",
        ]
        print("开始运行第 14 章因子表达式示例...")
        for expr in expressions:
            result = engine.run(expr)
            print(f"\nExpression: {expr}")
            print(result.tail(6))
        batch = engine.run_batch(expressions[:3])
        print("\nBatch Expressions:")
        print(batch.tail(6))
        print("done_textbook_ch14_factor")
    finally:
        if catalog_path.exists():
            shutil.rmtree(catalog_path)


if __name__ == "__main__":
    _run_demo()
