from __future__ import annotations

from typing import Optional


def calculate_option_margin(
    quantity: float,
    option_price: float,
    underlying_price: Optional[float],
    multiplier: float,
    margin_ratio: float,
    is_short: bool,
) -> float:
    """Calculate option margin requirement.

    Formula matches Rust src/margin/calculator.rs OptionMarginCalculator:
    - Long (not short): 0 margin
    - Short with underlying_price:
        (option_price + underlying_price * margin_ratio) * multiplier * abs(quantity)
    - Short without underlying_price:
        option_price * (1 + margin_ratio) * multiplier * abs(quantity)
    """
    if not is_short:
        return 0.0

    abs_qty = abs(quantity)
    opt_price = abs(option_price)

    if underlying_price is not None and underlying_price > 0:
        margin_per_unit = opt_price + abs(underlying_price) * abs(margin_ratio)
    else:
        margin_per_unit = opt_price * (1.0 + abs(margin_ratio))

    return margin_per_unit * abs(multiplier) * abs_qty
