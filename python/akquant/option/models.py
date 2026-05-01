from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OptionContract:
    """Option contract information."""

    symbol: str
    multiplier: float = 1.0
    margin_ratio: float = 0.1
    tick_size: float = 1.0
    option_type: Optional[str] = None
    strike_price: Optional[float] = None
    underlying_symbol: Optional[str] = None
    expiry_date: Optional[int] = None


@dataclass(frozen=True)
class OptionFeeConfig:
    """Option fee configuration."""

    commission_per_contract: float = 5.0
