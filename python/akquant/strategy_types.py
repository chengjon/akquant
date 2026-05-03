"""策略类型定义 (Strategy type definitions).

Extracted from strategy.py to reduce file size and improve maintainability.
"""

from dataclasses import dataclass, field
from typing import (
    Dict,
    Literal,
    Optional,
    Union,
    cast,
)


@dataclass
class StrategyRuntimeConfig:
    """策略运行时行为配置."""

    enable_precise_day_boundary_hooks: bool = False
    portfolio_update_eps: float = 0.0
    error_mode: Literal["raise", "continue", "legacy"] = "raise"
    re_raise_on_error: bool = True
    indicator_mode: Literal["incremental", "precompute"] = "precompute"

    def __post_init__(self) -> None:
        """校验并标准化配置."""
        self.portfolio_update_eps = float(self.portfolio_update_eps)
        if self.portfolio_update_eps < 0.0:
            raise ValueError("portfolio_update_eps must be >= 0")
        mode = str(self.error_mode).strip().lower()
        if mode not in {"raise", "continue", "legacy"}:
            raise ValueError("error_mode must be one of: raise, continue, legacy")
        self.error_mode = cast(Literal["raise", "continue", "legacy"], mode)
        indicator_mode = str(self.indicator_mode).strip().lower()
        if indicator_mode not in {"incremental", "precompute"}:
            raise ValueError("indicator_mode must be one of: incremental, precompute")
        self.indicator_mode = cast(Literal["incremental", "precompute"], indicator_mode)
        self.enable_precise_day_boundary_hooks = bool(
            self.enable_precise_day_boundary_hooks
        )
        self.re_raise_on_error = bool(self.re_raise_on_error)


InstrumentStaticValue = Union[str, int, float, bool]
InstrumentAssetTypeName = Literal["STOCK", "FUTURES", "FUND", "OPTION"]
InstrumentOptionTypeName = Literal["CALL", "PUT"]
InstrumentSettlementMode = Literal["CASH", "SETTLEMENT_PRICE", "FORCE_CLOSE"]


@dataclass(frozen=True)
class InstrumentSnapshot:
    """策略侧可访问的标的静态属性快照."""

    symbol: str
    asset_type: InstrumentAssetTypeName
    multiplier: float
    margin_ratio: float
    tick_size: float
    lot_size: float
    option_type: Optional[InstrumentOptionTypeName] = None
    strike_price: Optional[float] = None
    expiry_date: Optional[int] = None
    underlying_symbol: Optional[str] = None
    settlement_type: Optional[InstrumentSettlementMode] = None
    settlement_price: Optional[float] = None
    static_attrs: Dict[str, InstrumentStaticValue] = field(default_factory=dict)
