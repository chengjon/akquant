import logging
import shutil
import unittest
from pathlib import Path

import pandas as pd
import polars as pl
from akquant.data import ParquetDataCatalog
from akquant.factor import FactorEngine

logging.basicConfig(level=logging.INFO)


class TestFactorEngineNewOps(unittest.TestCase):
    """Test new time-series operators in FactorEngine."""

    def setUp(self) -> None:
        """Initialize test environment with temporary data."""
        self.catalog_path = Path("temp_test_catalog")
        if self.catalog_path.exists():
            shutil.rmtree(self.catalog_path)

        self.catalog = ParquetDataCatalog(root_path=str(self.catalog_path))

        # Create sample data
        # Symbol A: 1, 2, 3, 4, 5 -> Increasing
        # Symbol B: 5, 4, 3, 2, 1 -> Decreasing
        # Symbol C: 1, 5, 1, 5, 1 -> Volatile

        dates = pd.date_range("2023-01-01", periods=5)

        df_a = pd.DataFrame(
            {
                "date": dates,
                "open": [1, 2, 3, 4, 5],
                "close": [1, 2, 3, 4, 5],
                "symbol": "A",
            }
        ).set_index("date")

        df_b = pd.DataFrame(
            {
                "date": dates,
                "open": [5, 4, 3, 2, 1],
                "close": [5, 4, 3, 2, 1],
                "symbol": "B",
            }
        ).set_index("date")

        df_c = pd.DataFrame(
            {
                "date": dates,
                "open": [1, 5, 1, 5, 1],
                "close": [1, 5, 1, 5, 1],
                "symbol": "C",
            }
        ).set_index("date")

        self.catalog.write("A", df_a)
        self.catalog.write("B", df_b)
        self.catalog.write("C", df_c)

        self.engine = FactorEngine(self.catalog)

    def tearDown(self) -> None:
        """Clean up temporary test data."""
        if self.catalog_path.exists():
            shutil.rmtree(self.catalog_path)

    def test_ts_argmax(self) -> None:
        """Test Ts_ArgMax operator."""
        # Ts_ArgMax(Close, 3)
        # A: [1, 2, 3, 4, 5] -> Window 3
        # Day 2 (3): [1, 2, 3] -> Max is 3 (today) -> 0
        # Day 3 (4): [2, 3, 4] -> Max is 4 (today) -> 0
        # Day 4 (5): [3, 4, 5] -> Max is 5 (today) -> 0

        # B: [5, 4, 3, 2, 1] -> Window 3
        # Day 2 (3): [5, 4, 3] -> Max is 5 (2 days ago) -> 2
        # Day 3 (2): [4, 3, 2] -> Max is 4 (2 days ago) -> 2

        df = self.engine.run("Ts_ArgMax(Close, 3)")
        df = df.sort(["symbol", "date"])

        # Check A
        res_a = df.filter(pl.col("symbol") == "A")["factor_value"].to_list()
        # First 2 should be null (window not full)
        self.assertIsNone(res_a[0])
        self.assertIsNone(res_a[1])
        self.assertEqual(res_a[2], 0.0)
        self.assertEqual(res_a[3], 0.0)
        self.assertEqual(res_a[4], 0.0)

        # Check B
        res_b = df.filter(pl.col("symbol") == "B")["factor_value"].to_list()
        self.assertEqual(res_b[2], 2.0)
        self.assertEqual(res_b[3], 2.0)
        self.assertEqual(res_b[4], 2.0)

    def test_ts_argmin(self) -> None:
        """Test Ts_ArgMin operator."""
        # Ts_ArgMin(Close, 3)
        # A: [1, 2, 3, 4, 5] -> Min is oldest -> 2
        # B: [5, 4, 3, 2, 1] -> Min is newest -> 0

        df = self.engine.run("Ts_ArgMin(Close, 3)")
        df = df.sort(["symbol", "date"])

        # Check A
        res_a = df.filter(pl.col("symbol") == "A")["factor_value"].to_list()
        self.assertEqual(res_a[2], 2.0)

        # Check B
        res_b = df.filter(pl.col("symbol") == "B")["factor_value"].to_list()
        self.assertEqual(res_b[2], 0.0)

    def test_ts_rank(self) -> None:
        """Test Ts_Rank operator."""
        # Ts_Rank(Close, 3)
        # A: [1, 2, 3] -> 3 is rank 3 (largest) -> (3-1)/(3-1) = 1.0
        # B: [5, 4, 3] -> 3 is rank 1 (smallest) -> (1-1)/(3-1) = 0.0
        # C: [1, 5, 1] -> 1 is rank 1.5 (avg of 1st and 2nd smallest)
        # -> (1.5-1)/2 = 0.25

        df = self.engine.run("Ts_Rank(Close, 3)")
        df = df.sort(["symbol", "date"])

        # Check A
        res_a = df.filter(pl.col("symbol") == "A")["factor_value"].to_list()
        self.assertAlmostEqual(res_a[2], 1.0)

        # Check B
        res_b = df.filter(pl.col("symbol") == "B")["factor_value"].to_list()
        self.assertAlmostEqual(res_b[2], 0.0)

        # Check C
        # Day 2: [1, 5, 1] -> Last is 1. Rank 1.5. (1.5-1)/2 = 0.25
        res_c = df.filter(pl.col("symbol") == "C")["factor_value"].to_list()
        self.assertAlmostEqual(res_c[2], 0.25)

        # Day 3: [5, 1, 5] -> Last is 5. Sorted: [1, 5, 5]. Ranks: 1, 2.5, 2.5.
        # Last is 5. Rank 2.5. (2.5-1)/2 = 0.75
        self.assertAlmostEqual(res_c[3], 0.75)

    def test_rank_over_binary_expression_with_ts_operand(self) -> None:
        """Test Rank on binary expressions containing time-series operators."""
        df = pl.DataFrame(
            {
                "date": [
                    "2023-01-01",
                    "2023-01-01",
                    "2023-01-02",
                    "2023-01-02",
                    "2023-01-03",
                    "2023-01-03",
                ],
                "symbol": ["A", "B", "A", "B", "A", "B"],
                "high": [10.0, 20.0, 11.0, 20.0, 15.0, 20.0],
                "close": [9.0, 19.0, 10.0, 20.0, 11.0, 21.0],
            }
        )

        result = self.engine.run_on_data(df, "Rank(High-Ts_Mean(Close,2))")
        result = result.sort(["date", "symbol"])

        values = result["factor_value"].to_list()
        self.assertIsNone(values[0])
        self.assertIsNone(values[1])
        self.assertAlmostEqual(values[2], 1.0)
        self.assertAlmostEqual(values[3], 0.5)
        self.assertAlmostEqual(values[4], 1.0)
        self.assertAlmostEqual(values[5], 0.5)

    def test_robustness_renaming(self) -> None:
        """Test robustness of date column renaming."""
        # Clear existing catalog to avoid schema mismatch
        if self.catalog_path.exists():
            shutil.rmtree(self.catalog_path)
        self.catalog = ParquetDataCatalog(root_path=str(self.catalog_path))
        self.engine = FactorEngine(self.catalog)

        # Create data with "index" column instead of "date"
        df_idx = pd.DataFrame(
            {
                "index": pd.date_range("2023-01-01", periods=5),
                "close": [1, 2, 3, 4, 5],
                "symbol": "D",
            }
        )
        # Note: ParquetDataCatalog might enforce index, but let's try to bypass or mock
        # Writing directly to parquet file to simulate raw data
        path = self.catalog_path / "D"
        path.mkdir(parents=True, exist_ok=True)
        df_idx.to_parquet(path / "data.parquet")

        # Run engine
        # Should detect "index" and rename to "date"
        df = self.engine.run("Close", start_date="2023-01-01")
        cols = df.columns
        self.assertIn("date", cols)
        self.assertIn("symbol", cols)
        self.assertIn("factor_value", cols)

        # Check D exists
        res_d = df.filter(pl.col("symbol") == "D")
        self.assertEqual(len(res_d), 5)


if __name__ == "__main__":
    unittest.main()
