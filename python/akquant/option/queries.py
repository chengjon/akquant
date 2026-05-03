from __future__ import annotations

from typing import Optional


def calculate_option_margin(
    quantity: float,
    option_price: float,
    underlying_price: Optional[float],
    multiplier: float,
    margin_ratio: float,
    is_short: bool,
    strike: Optional[float] = None,
    option_type: Optional[str] = None,
) -> float:
    """Calculate option margin requirement.

    Formula matches Rust src/margin/calculator.rs OptionMarginCalculator
    using Chinese exchange standard:

    - Long (not short): 0 margin
    - Short with underlying_price and strike/option_type:
        Call short:
          otm = max(0, strike - underlying_price)
          margin = max(premium + max(0.12 * underlying - otm, 0.07 * underlying),
                       premium + underlying * margin_ratio)
        Put short:
          otm = max(0, underlying_price - strike)
          margin = max(premium + max(0.12 * underlying - otm, 0.07 * underlying),
                       premium + underlying * margin_ratio)
    - Short without strike/option_type (fallback):
        (option_price + underlying_price * margin_ratio) * multiplier * abs(quantity)
    - Short without underlying_price:
        option_price * (1 + margin_ratio) * multiplier * abs(quantity)
    """
    if not is_short:
        return 0.0

    abs_qty = abs(quantity)
    opt_price = abs(option_price)

    if underlying_price is not None and underlying_price > 0:
        ul_price = abs(underlying_price)

        if strike is not None and option_type is not None:
            # Chinese exchange standard formula
            option_type_upper = (
                option_type.upper() if isinstance(option_type, str) else ""
            )
            if option_type_upper == "CALL":
                otm = max(0.0, strike - ul_price)
            else:
                otm = max(0.0, ul_price - strike)

            term1_inner = max(0.12 * ul_price - otm, 0.07 * ul_price)
            term1 = opt_price + term1_inner
            term2 = opt_price + ul_price * abs(margin_ratio)
            margin_per_unit = max(term1, term2)
        else:
            # Fallback without strike/option_type
            margin_per_unit = opt_price + ul_price * abs(margin_ratio)
    else:
        margin_per_unit = opt_price * (1.0 + abs(margin_ratio))

    return margin_per_unit * abs(multiplier) * abs_qty
