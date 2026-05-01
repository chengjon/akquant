from __future__ import annotations


def calculate_margin(
    quantity: float,
    price: float,
    multiplier: float,
    margin_ratio: float,
) -> float:
    """计算期货保证金.

    公式: abs(quantity) * abs(price) * abs(multiplier) * abs(margin_ratio)
    与 Rust src/margin/calculator.rs FuturesMarginCalculator 一致.
    """
    return abs(quantity) * abs(price) * abs(multiplier) * abs(margin_ratio)


def calculate_notional(
    quantity: float,
    price: float,
    multiplier: float,
) -> float:
    """计算期货合约名义价值."""
    return abs(quantity) * abs(price) * abs(multiplier)
