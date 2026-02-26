from typing import Any, Callable, Dict, Union, cast

import polars as pl


def _to_expr(x: Any) -> pl.Expr:
    """Ensure input is a Polars Expression."""
    if isinstance(x, pl.Expr):
        return x
    # Check if it has rolling methods (duck typing) or just wrap
    if hasattr(x, "rolling"):
        return cast(pl.Expr, x)
    return pl.lit(x)


# --- Time Series Operators ---


def ts_mean(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling mean."""
    return _to_expr(x).rolling_mean(window_size=d).over("symbol")


def ts_std(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling standard deviation."""
    return _to_expr(x).rolling_std(window_size=d).over("symbol")


def ts_max(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling max."""
    return _to_expr(x).rolling_max(window_size=d).over("symbol")


def ts_min(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling min."""
    return _to_expr(x).rolling_min(window_size=d).over("symbol")


def ts_sum(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling sum."""
    return _to_expr(x).rolling_sum(window_size=d).over("symbol")


def ts_corr(x: Union[pl.Expr, float], y: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling correlation."""
    return pl.rolling_corr(_to_expr(x), _to_expr(y), window_size=d).over("symbol")


def ts_cov(x: Union[pl.Expr, float], y: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling covariance."""
    return pl.rolling_cov(_to_expr(x), _to_expr(y), window_size=d).over("symbol")


def delay(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Lag operator."""
    return _to_expr(x).shift(d).over("symbol")


def delta(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Difference operator: x(t) - x(t-d)."""
    x_expr = _to_expr(x)
    return (x_expr - x_expr.shift(d)).over("symbol")


def ts_argmax(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """
    Calculate rolling index of max value (days ago).

    0 = max was today, d-1 = max was d-1 days ago.
    """
    return (
        _to_expr(x)
        .cast(pl.Float64)
        .rolling_map(lambda s: float(d - 1 - (s.arg_max() or 0)), window_size=d)
        .over("symbol")
    )


def ts_argmin(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """
    Calculate rolling index of min value (days ago).

    0 = min was today, d-1 = min was d-1 days ago.
    """
    return (
        _to_expr(x)
        .cast(pl.Float64)
        .rolling_map(lambda s: float(d - 1 - (s.arg_min() or 0)), window_size=d)
        .over("symbol")
    )


def ts_rank(x: Union[pl.Expr, float], d: int) -> pl.Expr:
    """Calculate rolling rank of the current value within the window (0 to 1)."""

    def _rank_last(s: pl.Series) -> float:
        # Rank of the last element in the series
        if len(s) <= 1:
            return 0.0

        # Ensure floating point ranks
        r = s.rank(method="average")[-1]

        # Debugging (remove later)
        # print(f"Series: {s.to_list()}, Rank: {r}, Len: {len(s)}")

        return float((r - 1) / (len(s) - 1))

    return (
        _to_expr(x)
        .cast(pl.Float64)
        .rolling_map(_rank_last, window_size=d)
        .over("symbol")
    )


# --- Cross Sectional Operators ---


def rank(x: Union[pl.Expr, float]) -> pl.Expr:
    """Cross-sectional Rank (0 to 1)."""
    # pct=True gives 0..1? No, method='average' returns rank.
    # We normalize by count.
    # pl.count() -> pl.len() in modern Polars
    return _to_expr(x).rank(method="average").over("date") / pl.len().over("date")


def scale(x: Union[pl.Expr, float]) -> pl.Expr:
    """Scale x such that sum(abs(x)) = 1."""
    x_expr = _to_expr(x)
    return (x_expr / x_expr.abs().sum()).over("date")


def cs_standardize(x: Union[pl.Expr, float]) -> pl.Expr:
    """Z-Score Standardization: (x - mean) / std."""
    x_expr = _to_expr(x)
    return (x_expr - x_expr.mean().over("date")) / x_expr.std().over("date")


def cs_neutralize(x: Union[pl.Expr, float], group: Union[pl.Expr, str]) -> pl.Expr:
    """
    Neutralize x against a categorical group (e.g. Industry).

    Result = x - mean(x) within each group.
    """
    x_expr = _to_expr(x)
    # If group is a string literal passed from parser, it might be just a string
    # But parser converts Name to col. If user passed "industry", it's a string.
    # We should ensure it's an expression.
    if isinstance(group, str):
        # If it's a raw string, treat as column
        group_expr = pl.col(group)
    else:
        group_expr = _to_expr(group)

    # Calculate group mean for each date and group
    return x_expr - x_expr.mean().over(["date", group_expr])


def cs_winsorize(x: Union[pl.Expr, float], limit: float) -> pl.Expr:
    """Winsorize (Clip) at mean +/- limit * std."""
    x_expr = _to_expr(x)
    mean = x_expr.mean().over("date")
    std = x_expr.std().over("date")
    # Note: clip supports expressions in recent Polars versions
    return x_expr.clip(mean - limit * std, mean + limit * std)


def cs_winsorize_quantile(
    x: Union[pl.Expr, float], lower: float, upper: float
) -> pl.Expr:
    """Winsorize (Clip) at quantiles (e.g. 0.01, 0.99)."""
    x_expr = _to_expr(x)
    # Polars quantile aggregation supports over
    lo = x_expr.quantile(lower).over("date")
    up = x_expr.quantile(upper).over("date")
    return x_expr.clip(lo, up)


# --- Math/Logical Operators ---


def log(x: Union[pl.Expr, float]) -> pl.Expr:
    """Calculate natural logarithm."""
    return _to_expr(x).log()


def abs_val(x: Union[pl.Expr, float]) -> pl.Expr:
    """Calculate absolute value."""
    return _to_expr(x).abs()


def sign(x: Union[pl.Expr, float]) -> pl.Expr:
    """Calculate sign of value (-1, 0, 1)."""
    return _to_expr(x).sign()


def signed_power(x: Union[pl.Expr, float], e: float) -> pl.Expr:
    """Calculate signed power: sign(x) * abs(x)^e."""
    x_expr = _to_expr(x)
    return x_expr.sign() * x_expr.abs().pow(e)


def if_else(cond: Union[pl.Expr, bool], true_val: Any, false_val: Any) -> pl.Expr:
    """Return true_val if cond is true, else false_val."""
    # pl.when accepts boolean expr. true_val/false_val can be literals.
    return pl.when(cond).then(true_val).otherwise(false_val)


# --- Map ---

OPS_MAP: Dict[str, Callable] = {
    # Time Series
    "Ts_Mean": ts_mean,
    "Mean": ts_mean,
    "Ts_Std": ts_std,
    "Std": ts_std,
    "Ts_Max": ts_max,
    "Max": ts_max,
    "Ts_Min": ts_min,
    "Min": ts_min,
    "Ts_Sum": ts_sum,
    "Sum": ts_sum,
    "Ts_Corr": ts_corr,
    "Corr": ts_corr,
    "Ts_Cov": ts_cov,
    "Cov": ts_cov,
    "Delay": delay,
    "Ref": delay,  # Common alias
    "Delta": delta,
    # New Time Series
    "Ts_ArgMax": ts_argmax,
    "ArgMax": ts_argmax,
    "Ts_ArgMin": ts_argmin,
    "ArgMin": ts_argmin,
    "Ts_Rank": ts_rank,
    # Cross Section
    "Rank": rank,
    "Scale": scale,
    "Standardize": cs_standardize,
    "ZScore": cs_standardize,  # Alias
    "Winsorize": cs_winsorize,
    "WinsorizeQuantile": cs_winsorize_quantile,
    "Neutralize": cs_neutralize,
    "IndNeutralize": cs_neutralize,  # Alias
    # Math
    "Log": log,
    "Abs": abs_val,
    "Sign": sign,
    "SignedPower": signed_power,
    "If": if_else,
}

# Define Operator Categories for Parser Optimization
# TS: Time-Series (over symbol)
# CS: Cross-Sectional (over date)
# EL: Element-wise (neutral)
OP_CATEGORY: Dict[str, str] = {
    # TS
    "Ts_Mean": "TS",
    "Mean": "TS",
    "Ts_Std": "TS",
    "Std": "TS",
    "Ts_Max": "TS",
    "Max": "TS",
    "Ts_Min": "TS",
    "Min": "TS",
    "Ts_Sum": "TS",
    "Sum": "TS",
    "Ts_Corr": "TS",
    "Corr": "TS",
    "Ts_Cov": "TS",
    "Cov": "TS",
    "Delay": "TS",
    "Ref": "TS",
    "Delta": "TS",
    "Ts_ArgMax": "TS",
    "ArgMax": "TS",
    "Ts_ArgMin": "TS",
    "ArgMin": "TS",
    "Ts_Rank": "TS",
    # CS
    "Rank": "CS",
    "Scale": "CS",
    "Standardize": "CS",
    "ZScore": "CS",
    "Winsorize": "CS",
    "WinsorizeQuantile": "CS",
    "Neutralize": "CS",
    "IndNeutralize": "CS",
    # EL
    "Log": "EL",
    "Abs": "EL",
    "Sign": "EL",
    "SignedPower": "EL",
    "If": "EL",
}
