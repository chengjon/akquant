import polars as pl
import pytest
from akquant.factor.ops import (
    cs_neutralize,
    cs_standardize,
    cs_winsorize,
    cs_winsorize_quantile,
)
from akquant.factor.parser import ExpressionParser


@pytest.fixture
def sample_data() -> pl.DataFrame:
    """Create sample data for testing cross-sectional ops."""
    return pl.DataFrame(
        {
            "date": ["2023-01-01"] * 4 + ["2023-01-02"] * 4,
            "symbol": ["A", "B", "C", "D", "A", "B", "C", "D"],
            "value": [1.0, 2.0, 3.0, 100.0, 10.0, 20.0, 30.0, 40.0],  # 100 is outlier
            "sector": ["T", "T", "F", "F", "T", "T", "F", "F"],  # Tech, Finance
        }
    )


def test_standardize(sample_data: pl.DataFrame) -> None:
    """Test Z-Score standardization."""
    df = sample_data.with_columns(zscore=cs_standardize(pl.col("value")))

    # Check mean and std per date
    stats = df.group_by("date").agg(
        mean=pl.col("zscore").mean(), std=pl.col("zscore").std()
    )

    # Allow small floating point errors
    assert abs(stats["mean"][0]) < 1e-6
    assert abs(stats["std"][0] - 1.0) < 1e-6


def test_winsorize(sample_data: pl.DataFrame) -> None:
    """Test 3-sigma winsorization."""
    # With value=[1, 2, 3, 100], mean=26.5, std=49.0
    # 3-sigma is huge, let's use smaller sigma to force clip
    # Mean=26.5, Std=49. limit=0.5 -> range [26.5 - 24.5, 26.5 + 24.5] = [2.0, 51.0]
    # So 1.0 should be clipped to 2.0? No, 1.0 < 2.0.
    # Wait, mean-0.5*std = 26.5 - 24.5 = 2.0. 1.0 < 2.0, so 1.0 becomes 2.0.
    # 100 > 51.0, so 100 becomes 51.0.

    df = sample_data.with_columns(clipped=cs_winsorize(pl.col("value"), limit=0.5))

    # Check day 1
    day1 = df.filter(pl.col("date") == "2023-01-01")
    vals = day1["clipped"].to_list()

    # Original: 1, 2, 3, 100
    # Mean=26.5, Std=49.05
    # Limit=0.5
    # Lower = 26.5 - 24.525 = 1.975
    # Upper = 26.5 + 24.525 = 51.025

    # 1.0 -> 1.975 (approx)
    # 2.0 -> 2.0 (unchanged)
    # 3.0 -> 3.0 (unchanged)
    # 100.0 -> 51.025 (approx)

    assert vals[0] > 1.0  # Clipped up
    assert vals[3] < 100.0  # Clipped down
    assert vals[1] == 2.0  # Unchanged


def test_winsorize_quantile(sample_data: pl.DataFrame) -> None:
    """Test quantile winsorization."""
    # Clip at 25% and 75%
    # Values: 1, 2, 3, 100
    # 25% ~ 1.75? 75% ~ 27.25?

    df = sample_data.with_columns(
        clipped=cs_winsorize_quantile(pl.col("value"), lower=0.25, upper=0.75)
    )

    day1 = df.filter(pl.col("date") == "2023-01-01")
    vals = day1["clipped"].to_list()

    # Bounds should be between min and max
    assert vals[0] >= day1["value"].quantile(0.25)
    assert vals[3] <= day1["value"].quantile(0.75)


def test_neutralize(sample_data: pl.DataFrame) -> None:
    """Test industry neutralization."""
    # Neutralize value by sector
    df = sample_data.with_columns(
        neutral=cs_neutralize(pl.col("value"), pl.col("sector"))
    )

    # Mean of neutral within each sector/date should be 0
    stats = df.group_by(["date", "sector"]).agg(mean=pl.col("neutral").mean())

    for m in stats["mean"]:
        assert abs(m) < 1e-6


def test_parser_integration(sample_data: pl.DataFrame) -> None:
    """Test parser integration."""
    parser = ExpressionParser()

    # Test Neutralize(value, sector)
    expr = parser.parse("Neutralize(value, sector)")
    df = sample_data.with_columns(res=expr)
    assert df["res"].null_count() == 0

    # Test Standardize(value)
    expr = parser.parse("Standardize(value)")
    df2 = sample_data.with_columns(res=expr)
    assert df2["res"].null_count() == 0

    # Test Winsorize(value, 3.0)
    expr = parser.parse("Winsorize(value, 3.0)")
    df3 = sample_data.with_columns(res=expr)
    assert df3["res"].null_count() == 0
