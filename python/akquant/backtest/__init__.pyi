from typing import Any, Callable, Dict, List, Optional, Type, Union

import pandas as pd

from ..akquant import AssetType, Bar, DataFeed, ExecutionMode
from ..config import BacktestConfig, RiskConfig
from ..strategy import Strategy, StrategyRuntimeConfig
from .result import BacktestResult

class FunctionalStrategy(Strategy):
    def __init__(
        self,
        initialize: Optional[Callable[[Any], None]],
        on_bar: Optional[Callable[[Any, Bar], None]],
        on_tick: Optional[Callable[[Any, Any], None]] = ...,
        on_order: Optional[Callable[[Any, Any], None]] = ...,
        on_trade: Optional[Callable[[Any, Any], None]] = ...,
        on_timer: Optional[Callable[[Any, str], None]] = ...,
        context: Optional[Dict[str, Any]] = None,
    ) -> None: ...

def run_backtest(
    data: Optional[
        Union[pd.DataFrame, Dict[str, pd.DataFrame], List[Bar], DataFeed]
    ] = ...,
    strategy: Union[Type[Strategy], Strategy, Callable[[Any, Bar], None], None] = ...,
    symbol: Union[str, List[str]] = ...,
    initial_cash: Optional[float] = ...,
    commission_rate: Optional[float] = ...,
    stamp_tax_rate: float = ...,
    transfer_fee_rate: float = ...,
    min_commission: float = ...,
    slippage: Optional[float] = ...,
    volume_limit_pct: Optional[float] = ...,
    execution_mode: Union[ExecutionMode, str] = ...,
    timezone: Optional[str] = ...,
    t_plus_one: bool = ...,
    initialize: Optional[Callable[[Any], None]] = ...,
    on_tick: Optional[Callable[[Any, Any], None]] = ...,
    on_order: Optional[Callable[[Any, Any], None]] = ...,
    on_trade: Optional[Callable[[Any, Any], None]] = ...,
    on_timer: Optional[Callable[[Any, str], None]] = ...,
    context: Optional[Dict[str, Any]] = ...,
    history_depth: Optional[int] = ...,
    warmup_period: int = ...,
    lot_size: Union[int, Dict[str, int], None] = ...,
    show_progress: Optional[bool] = ...,
    start_time: Optional[Union[str, Any]] = ...,
    end_time: Optional[Union[str, Any]] = ...,
    config: Optional[BacktestConfig] = ...,
    custom_matchers: Optional[Dict[AssetType, Any]] = ...,
    risk_config: Optional[Union[Dict[str, Any], RiskConfig]] = ...,
    strategy_runtime_config: Optional[
        Union[StrategyRuntimeConfig, Dict[str, Any]]
    ] = ...,
    runtime_config_override: bool = ...,
    **kwargs: Any,
) -> BacktestResult: ...
def run_warm_start(
    checkpoint_path: str,
    data: Optional[
        Union[pd.DataFrame, Dict[str, pd.DataFrame], List[Bar], DataFeed]
    ] = ...,
    show_progress: bool = ...,
    symbol: Union[str, List[str]] = ...,
    strategy_runtime_config: Optional[
        Union[StrategyRuntimeConfig, Dict[str, Any]]
    ] = ...,
    runtime_config_override: bool = ...,
    **kwargs: Any,
) -> BacktestResult: ...

__all__ = [
    "BacktestResult",
    "run_backtest",
    "run_warm_start",
    "FunctionalStrategy",
]
