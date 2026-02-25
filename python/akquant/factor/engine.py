import logging
from typing import List, Optional

import polars as pl

from ..data import ParquetDataCatalog
from .parser import ExpressionParser

logger = logging.getLogger(__name__)


class FactorEngine:
    """Engine for calculating factors using Polars Lazy API."""

    def __init__(self, catalog: ParquetDataCatalog):
        """Initialize the FactorEngine with a data catalog."""
        self.catalog = catalog
        self.parser = ExpressionParser()

    def load_data(self) -> pl.LazyFrame:
        """
        Load all data from catalog as a LazyFrame.

        Assumes data is partitioned by symbol or simply stored in separate files.
        """
        # We look for all parquet files under the root
        # Pattern: root/**/data.parquet
        # This covers:
        # - root/AAPL/data.parquet (ParquetDataCatalog default)
        # - root/symbol=AAPL/data.parquet (Hive style)
        pattern = str(self.catalog.root / "**" / "*.parquet")

        try:
            # use_pyarrow=True often helps with nested paths compatibility
            lf = pl.scan_parquet(pattern)
            return lf
        except Exception as e:
            logger.warning(f"Failed to scan parquet files: {e}")
            return pl.DataFrame().lazy()

    def _ensure_date_column(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Ensure 'date' column exists, renaming from common variants if needed."""
        # Check schema to find date column
        # Note: collect_schema() is preferred in newer Polars, .schema in older
        try:
            schema = lf.collect_schema()
        except AttributeError:
            schema = lf.schema  # type: ignore

        cols = schema.names() if hasattr(schema, "names") else list(schema.keys())
        logger.info(f"Detected columns: {cols}")

        if "date" in cols:
            return lf
        elif "index" in cols:
            return lf.rename({"index": "date"})
        elif "datetime" in cols:
            return lf.rename({"datetime": "date"})
        elif "__index_level_0__" in cols:
            return lf.rename({"__index_level_0__": "date"})
        else:
            # Fallback: assume user knows what they are doing or it will fail later
            logger.warning(
                f"Could not identify 'date' column from {cols}. "
                "Expecting 'date', 'index', 'datetime', or '__index_level_0__'."
            )
            return lf

    def run(
        self,
        expr_str: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """
        Execute a factor expression.

        :param expr_str: The factor expression string (e.g., "Rank(Ts_Mean(Close, 5))")
        :param start_date: Filter start date (inclusive).
        :param end_date: Filter end date (inclusive).
        :return: DataFrame with [date, symbol, factor] columns.
        """
        logger.info(f"Parsing expression: {expr_str}")
        factor_expr = self.parser.parse(expr_str)

        lf = self.load_data()
        lf = self._ensure_date_column(lf)

        # Sort is crucial for rolling window functions
        lf = lf.sort(["symbol", "date"])

        # Handle date filtering
        # Convert string dates to datetime literals for comparison
        if start_date:
            lf = lf.filter(
                pl.col("date") >= pl.lit(start_date).str.to_datetime(strict=False)
            )
        if end_date:
            lf = lf.filter(
                pl.col("date") <= pl.lit(end_date).str.to_datetime(strict=False)
            )

        # Select and Compute
        result_lf = lf.select(
            [pl.col("date"), pl.col("symbol"), factor_expr.alias("factor_value")]
        )

        # Collect results
        logger.info("Executing query plan...")
        df = result_lf.collect()
        return df

    def run_batch(self, exprs: List[str]) -> pl.DataFrame:
        """Run multiple expressions at once."""
        lf = self.load_data()
        lf = self._ensure_date_column(lf)
        lf = lf.sort(["symbol", "date"])

        selections = [pl.col("date"), pl.col("symbol")]
        for i, expr_str in enumerate(exprs):
            expr = self.parser.parse(expr_str)
            selections.append(expr.alias(f"factor_{i}"))

        return lf.select(selections).collect()
